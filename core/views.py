from django.http import JsonResponse


def health_check(request):
    """Simple health check endpoint to confirm the app is running."""
    return JsonResponse({"status": "ok", "service": "clinic-system"})
