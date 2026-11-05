from django.http import JsonResponse
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Liveness probe. Touches no database, so it works even if the DB is down."""

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "ok"})


class ApiNotFoundView(APIView):
    """Catch-all for unknown URLs under /api/: a JSON 404 for any HTTP method.

    Without it Django answers with an HTML page (always when DEBUG is true).
    """

    authentication_classes = []
    permission_classes = []

    def initial(self, request, *args, **kwargs):
        raise NotFound("Not found.")


# --- Django-level handlers for URLs outside /api/ (used when DEBUG is false) ---
def bad_request(request, exception=None):
    return JsonResponse({"error": "Bad request.", "code": 400}, status=400)


def permission_denied(request, exception=None):
    return JsonResponse({"error": "Forbidden.", "code": 403}, status=403)


def not_found(request, exception=None):
    return JsonResponse({"error": "Not found.", "code": 404}, status=404)