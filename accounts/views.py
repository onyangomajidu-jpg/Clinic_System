from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def dashboard(request):
    """
    Role-aware landing page shown right after login.

    This is a thin UI layer: it shows each role only the menu cards that
    make sense for them (UR-10 -- fast, uncluttered access on a shared
    device), but it is not itself the access-control boundary. The real
    enforcement is Django's permission system (see accounts.permissions,
    accounts.signals) which governs both /admin/ and any future dedicated
    views built with accounts.decorators.role_required /
    accounts.mixins.RoleRequiredMixin.
    """
    staff = getattr(request.user, "staff_profile", None)
    context = {
        "staff": staff,
        "can_manage_patients": request.user.has_perm("core.view_patient"),
        "can_manage_visits": request.user.has_perm("core.view_visit"),
        "can_manage_pharmacy": request.user.has_perm("core.view_drug"),
        "can_manage_billing": request.user.has_perm("core.view_invoice"),
        "can_manage_lab": request.user.has_perm("core.view_labtest"),
        "can_manage_staff": request.user.has_perm("core.view_staff"),
    }
    return render(request, "accounts/dashboard.html", context)
