import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.models import Staff


class Command(BaseCommand):
    """Idempotently create/update the initial admin (superuser + Admin staff).

    Reads the login details from environment variables so a fresh deployment
    (e.g. on Render, where the DB starts empty) gets a usable admin account
    automatically without anyone running interactive prompts:

        DJANGO_ADMIN_USERNAME   (default: admin)
        DJANGO_ADMIN_EMAIL      (default: admin@example.com)
        DJANGO_ADMIN_PASSWORD   (no default - required)

    Safe to run on every container start: if the username already exists the
    password/email are reset to the current env values and the staff record is
    re-linked, so the credentials always match what the env says. Existing
    password (or the whole account) is NOT touched if the env vars are absent.

    Note: only a superuser can create further auth accounts and assign roles
    (see accounts.permissions), so this is the single bootstrap that unlocks
    the rest of staff administration.
    """

    help = (
        "Create/update the initial admin user and Admin staff record from "
        "DJANGO_ADMIN_USERNAME / DJANGO_ADMIN_EMAIL / DJANGO_ADMIN_PASSWORD. "
        "Idempotent - safe to run on every deploy."
    )

    def handle(self, *args, **options):
        User = get_user_model()

        username = os.getenv("DJANGO_ADMIN_USERNAME", "").strip() or "admin"
        email = os.getenv("DJANGO_ADMIN_EMAIL", "").strip() or "admin@example.com"
        password = os.getenv("DJANGO_ADMIN_PASSWORD", "").strip()

        if not password:
            self.stderr.write(
                self.style.WARNING(
                    "DJANGO_ADMIN_PASSWORD not set - skipping admin creation. "
                    "Set it (along with DJANGO_ADMIN_USERNAME) in the environment "
                    "to auto-provision the initial admin."
                )
            )
            return

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        # Always enforce superuser/staff/active and reset the password to the
        # configured one so the admin can never lose access due to stale state.
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()

        # Link/create the Admin staff record. Staff.post_save syncs groups and
        # is_staff, giving this account the "Admin / In-charge" clinic role.
        staff, staff_created = Staff.objects.get_or_create(
            user=user,
            defaults={"name": "System Administrator", "role": Staff.Role.ADMIN},
        )
        if not staff_created and staff.role != Staff.Role.ADMIN:
            staff.role = Staff.Role.ADMIN
            staff.save()

        verb = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} admin login: username='{username}' "
                f"email='{email}' staff={'created' if staff_created else 'linked'}"
            )
        )