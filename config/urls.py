from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from categories.views import CategoryViewSet
from core.views import ApiNotFoundView, HealthView
from todos.views import TodoViewSet
from teams.views import TeamViewSet
from accounts.views import AdminUserViewSet
from notifications.views import NotificationViewSet
from dashboard.views import (
    AdminTodoDetailView,
    AdminUserTodosView,
    DashboardActivityView,
    DashboardTeamsView,
    DashboardUsersView,
    OverviewView,
)

# Default routes, but without the trailing slash: /api/categories, /api/categories/1
router = DefaultRouter(trailing_slash=False)
router.include_format_suffixes = False  # no /api/categories.json variants
router.register("categories", CategoryViewSet, basename="category")
router.register("todos", TodoViewSet, basename="todo")
router.register("teams", TeamViewSet, basename="team")
router.register("admin/users", AdminUserViewSet, basename="admin-user")
router.register("notifications", NotificationViewSet, basename="notification")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health", HealthView.as_view(), name="health"),
    path("api/schema", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    
    path("api/auth/", include("accounts.urls")),
    path("api/", include(router.urls)),
    path("api/admin/dashboard/overview", OverviewView.as_view(), name="admin-dashboard-overview"),
    path("api/admin/dashboard/users", DashboardUsersView.as_view(), name="admin-dashboard-users"),
    path("api/admin/dashboard/teams", DashboardTeamsView.as_view(), name="admin-dashboard-teams"),
    path("api/admin/dashboard/activity", DashboardActivityView.as_view(), name="admin-dashboard-activity"),
    path("api/admin/users/<int:user_id>/todos", AdminUserTodosView.as_view(), name="admin-user-todos"),
    path("api/admin/todos/<int:todo_id>", AdminTodoDetailView.as_view(), name="admin-todo-detail"),
    # Must stay last: any other /api/... URL is a JSON 404.
    path("api/<path:unknown>", ApiNotFoundView.as_view(), name="api-not-found"),
]

# Errors for URLs outside /api/ and Django-level failures (used when DEBUG is false).
handler400 = "core.views.bad_request"
handler403 = "core.views.permission_denied"
handler404 = "core.views.not_found"
handler500 = "core.views.server_error"