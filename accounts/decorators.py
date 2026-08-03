from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """
    Restrict a function-based view to logged-in staff whose Staff.role is
    one of `roles`.

    Use this for access decisions that hinge on *who someone is* rather
    than *what they're doing to a specific record* -- for the latter,
    prefer Django's built-in @permission_required against the model
    permissions set up in accounts.permissions, since those already cover
    add/change/delete/view per role and stay in one declarative place.

    Usage:
        @role_required(Staff.Role.ADMIN)
        def staff_accounts(request):
            ...
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            staff = getattr(request.user, "staff_profile", None)
            if staff is None or staff.role not in roles:
                raise PermissionDenied("Your role does not have access to this page.")
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator
