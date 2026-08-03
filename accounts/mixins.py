from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class RoleRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """
    Class-based-view equivalent of accounts.decorators.role_required.

    Subclasses set `allowed_roles`, e.g.:

        class StaffAccountListView(RoleRequiredMixin, ListView):
            allowed_roles = (Staff.Role.ADMIN,)
            model = Staff

    Unauthenticated users are redirected to log in (LoginRequiredMixin);
    authenticated users whose role isn't in allowed_roles get a 403
    (UserPassesTestMixin's default raise_exception behaviour).
    """

    allowed_roles = ()
    raise_exception = True

    def test_func(self):
        staff = getattr(self.request.user, "staff_profile", None)
        return bool(staff and staff.role in self.allowed_roles)
