"""CSRF failure diagnostics for the clinic_system project.

Django's CSRF rejection page hides the exact reason when DEBUG=False, which
makes CSRF 403s (e.g. on the admin login) very hard to diagnose in production
(Render). This middleware NEVER alters request/response behavior — it only
writes a warning line to the server logs whenever a POST is answered with 403,
including the headers Django's CsrfViewMiddleware bases its decision on.
"""
import logging

from django.conf import settings

logger = logging.getLogger("clinic.csrf")


class CsrfDiagnosticsMiddleware:
    """Log header context for any 403 answered to a POST (inert otherwise)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method == "POST" and response.status_code == 403:
            try:
                logger.warning(
                    "CSRF/403 diagnostic: path=%s | Host=%s | scheme=%s | secure=%s | "
                    "Origin=%s | Referer=%s | csrftoken cookie sent=%s | "
                    "CSRF_TRUSTED_ORIGINS=%s | SECURE_SSL_REDIRECT=%s",
                    request.get_full_path(),
                    request.get_host(),
                    request.scheme,
                    request.is_secure(),
                    request.headers.get("Origin", "<absent>"),
                    request.headers.get("Referer", "<absent>"),
                    "yes"
                    if getattr(settings, "CSRF_COOKIE_NAME", "csrftoken") in request.COOKIES
                    else "NO (cookie missing/blocked — likely cause: Secure cookie over http, cleared cookies, or cookies disabled)",
                    getattr(settings, "CSRF_TRUSTED_ORIGINS", []),
                    getattr(settings, "SECURE_SSL_REDIRECT", False),
                )
            except Exception:  # diagnostics must never break the app
                logger.warning("CSRF/403 diagnostic: could not collect headers", exc_info=True)
        return response
