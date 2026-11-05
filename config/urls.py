from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from categories.views import CategoryViewSet
from core.views import HealthView
from todos.views import TodoViewSet

# Default routes, but without the trailing slash: /api/categories, /api/categories/1
router = DefaultRouter(trailing_slash=False)
router.include_format_suffixes = False  # no /api/categories.json variants
router.register("categories", CategoryViewSet, basename="category")
outer.register("todos", TodoViewSet, basename="todo")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health", HealthView.as_view(), name="health"),
    path("api/", include(router.urls)),
]