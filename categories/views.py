from django.conf import settings
from django.core.cache import cache
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from . import cache as category_cache
from .models import Category
from .permissions import CategoryPermissions
from .serializers import CategorySerializer


class CategoryViewSet(ModelViewSet):
    """Categories are global: every user can read them, only admins can change them."""

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [CategoryPermissions]
    # A small, admin-managed list that dropdowns need in full: not paginated.
    pagination_class = None
    # Plain ASCII digits, no leading zero, at most 18 digits (fits SQLite's
    # 64-bit integer). Everything else (abc, 0, 007, Bangla digits) is a 404.
    lookup_value_regex = r"[1-9][0-9]{0,17}"
    # PATCH (partial update) only; PUT is intentionally not supported.
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def list(self, request, *args, **kwargs):
        """Cached list. Authentication and permissions already ran, so serving
        the shared entry never bypasses them. The query string is ignored on
        purpose: it has no effect on this endpoint, and honouring it would let
        anyone fill the cache with junk keys."""
        # Read the version BEFORE the database: if a category changes while we
        # work, our (now stale) result is stored under the old version, which
        # nobody reads any more.
        key = category_cache.list_key(category_cache.current_version())
        data = cache.get(key)
        if isinstance(data, list):
            return Response(data, headers={"X-Cache": "HIT"})

        queryset = self.filter_queryset(self.get_queryset())
        data = [dict(item) for item in self.get_serializer(queryset, many=True).data]
        cache.set(key, data, settings.CATEGORY_CACHE_SECONDS)
        return Response(data, headers={"X-Cache": "MISS"})