from io import StringIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core.models import Staff


class CreateAdminCommandTests(TestCase):
    """accounts.management.commands.create_admin - provisions the initial
    superuser + Admin staff record from DJANGO_ADMIN_* env vars."""

    def _run(self, **env):
        with mock.patch.dict("os.environ", env, clear=False):
            return call_command("create_admin", stdout=StringIO(), stderr=StringIO())

    def test_creates_superuser_and_admin_staff(self):
        self._run(
            DJANGO_ADMIN_USERNAME="admin",
            DJANGO_ADMIN_EMAIL="admin@example.com",
            DJANGO_ADMIN_PASSWORD="Secret-123!",
        )

        user = User.objects.get(username="admin")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password("Secret-123!"))

        staff = Staff.objects.get(user=user)
        self.assertEqual(staff.role, Staff.Role.ADMIN)

    def test_idempotent_when_admin_exists(self):
        self._run(
            DJANGO_ADMIN_USERNAME="admin",
            DJANGO_ADMIN_PASSWORD="First-123!",
        )
        self._run(
            DJANGO_ADMIN_USERNAME="admin",
            DJANGO_ADMIN_EMAIL="new@example.com",
            DJANGO_ADMIN_PASSWORD="Second-123!",
        )

        user = User.objects.get(username="admin")
        self.assertEqual(User.objects.filter(username="admin").count(), 1)
        self.assertEqual(Staff.objects.filter(user=user).count(), 1)
        self.assertTrue(user.check_password("Second-123!"))
        self.assertEqual(user.email, "new@example.com")

    def test_skips_when_password_missing(self):
        out = StringIO()
        err = StringIO()
        with mock.patch.dict("os.environ", {}, clear=False):
            call_command("create_admin", stdout=out, stderr=err)
        self.assertFalse(User.objects.filter(username="admin").exists())
        self.assertIn("DJANGO_ADMIN_PASSWORD", err.getvalue())


class RoleGroupSyncTests(TestCase):
    """accounts.signals.sync_role_groups runs automatically post-migrate
    (via the test runner's own migration step), so by the time these tests
    run, one Group per Staff.Role should already exist with the right
    permissions attached."""

    def test_every_role_has_a_group(self):
        from django.contrib.auth.models import Group

        role_names = {choice.value for choice in Staff.Role}
        group_names = set(Group.objects.values_list("name", flat=True))
        self.assertTrue(role_names.issubset(group_names))

    def test_admin_group_has_full_core_access(self):
        from django.contrib.auth.models import Group

        admin_group = Group.objects.get(name=Staff.Role.ADMIN)
        codenames = set(admin_group.permissions.values_list("codename", flat=True))
        for action in ("view", "add", "change", "delete"):
            self.assertIn(f"{action}_patient", codenames)
            self.assertIn(f"{action}_staff", codenames)

    def test_receptionist_cannot_manage_drug_stock(self):
        from django.contrib.auth.models import Group

        group = Group.objects.get(name=Staff.Role.RECEPTIONIST)
        codenames = set(group.permissions.values_list("codename", flat=True))
        self.assertNotIn("add_drug", codenames)
        self.assertNotIn("change_drug", codenames)


class StaffAccountSyncTests(TestCase):
    """Staff <-> User linkage: group membership, is_staff, and is_active
    should all stay in sync with the Staff record (accounts.signals)."""

    def setUp(self):
        self.user = User.objects.create_user("j.nurse", password="TestPass123!")
        self.staff = Staff.objects.create(
            user=self.user, name="Joy Nabirye", role=Staff.Role.NURSE
        )

    def test_user_is_added_to_role_group(self):
        self.user.refresh_from_db()
        self.assertIn("nurse", [g.name for g in self.user.groups.all()])
        self.assertTrue(self.user.is_staff)

    def test_role_change_updates_group_membership(self):
        self.staff.role = Staff.Role.ADMIN
        self.staff.save()
        self.user.refresh_from_db()
        group_names = [g.name for g in self.user.groups.all()]
        self.assertIn("admin", group_names)
        self.assertNotIn("nurse", group_names)

    def test_deactivating_staff_deactivates_login(self):
        self.staff.is_active = False
        self.staff.save()
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)


class LoginFlowTests(TestCase):
    def setUp(self):
        self.active_user = User.objects.create_user("dr.who", password="TestPass123!")
        Staff.objects.create(user=self.active_user, name="Dr. Who", role=Staff.Role.DOCTOR)

        self.inactive_user = User.objects.create_user("old.staff", password="TestPass123!")
        Staff.objects.create(
            user=self.inactive_user, name="Old Staff", role=Staff.Role.NURSE, is_active=False
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_wrong_password_shows_friendly_error(self):
        response = self.client.post(
            reverse("accounts:login"), {"username": "dr.who", "password": "wrong"}
        )
        self.assertEqual(response.status_code, 200)
        # Rendered HTML escapes the apostrophe as &#x27;
        self.assertContains(response, "wasn")
        self.assertContains(response, "right")

    def test_deactivated_staff_cannot_log_in(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "old.staff", "password": "TestPass123!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "deactivated")

    def test_active_staff_can_log_in_and_reach_dashboard(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "dr.who", "password": "TestPass123!"},
            follow=True,
        )
        self.assertContains(response, "Welcome")
        self.assertContains(response, "Doctor")

    def test_logout_redirects_to_login(self):
        self.client.login(username="dr.who", password="TestPass123!")
        response = self.client.post(reverse("accounts:logout"), follow=True)
        self.assertContains(response, "Sign in to continue")
