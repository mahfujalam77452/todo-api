from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from categories.views import CategoryViewSet
from core.views import ApiNotFoundView, HealthView
from todos.views import TodoViewSet

# Default routes, but without the trailing slash: /api/categories, /api/categories/1
router = DefaultRouter(trailing_slash=False)
router.include_format_suffixes = False  # no /api/categories.json variants
router.register("categories", CategoryViewSet, basename="category")
router.register("todos", TodoViewSet, basename="todo")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health", HealthView.as_view(), name="health"),
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    
    path("api/auth/", include("accounts.urls")),
    path("api/", include(router.urls)),
    # Must stay last: any other /api/... URL is a JSON 404.
    path("api/<path:unknown>", ApiNotFoundView.as_view(), name="api-not-found"),
]

# Errors for URLs outside /api/ and Django-level failures (used when DEBUG is false).
handler400 = "core.views.bad_request"
handler403 = "core.views.permission_denied"
handler404 = "core.views.not_found"
handler500 = "core.views.server_error"