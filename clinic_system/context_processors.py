"""Context processors for the clinic_system project.

These make site-wide values (clinic name, logo path) available to every
template without each view having to pass them explicitly.
"""
from django.conf import settings


def clinic_info(request):
    """Expose the clinic name and logo URL to all templates.

    The clinic name is read from the ``CLINIC_NAME`` setting (which can be
    overridden via the ``CLINIC_NAME`` environment variable in ``.env``).
    The logo is served from the static directory as ``logo.png``.
    """
    return {
        "clinic_name": getattr(settings, "CLINIC_NAME", "ALHAMA MEDICAL CLINIC"),
        "clinic_logo": getattr(settings, "CLINIC_LOGO_URL", "/static/logo.png"),
    }
