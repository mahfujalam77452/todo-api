from rest_framework.viewsets import ModelViewSet

from .models import Category
from .serializers import CategorySerializer


class CategoryViewSet(ModelViewSet):
    """CRUD for categories. Write access is restricted to admins in Task 4.5."""

    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    # Only digits that fit a 64-bit integer, so /categories/abc and absurdly
    # large ids are a clean 404 instead of an overflow error in SQLite.
    lookup_value_regex = r"\d{1,18}"
    # PATCH (partial update) only; PUT is intentionally not supported.
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]