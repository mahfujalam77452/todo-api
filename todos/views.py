from rest_framework.viewsets import ModelViewSet

from .filters import TodoFilter
from .models import Todo
from .serializers import TodoSerializer


class TodoViewSet(ModelViewSet):
    # select_related: category_name is read for every row, so fetch it with the
    # todos in one query instead of one extra query per todo (N+1).
    # Ordering comes from Todo.Meta: newest first, id as the tie-breaker.
    queryset = Todo.objects.select_related("category")
    serializer_class = TodoSerializer
    filterset_class = TodoFilter
    # Plain ASCII digits, no leading zero, at most 18 digits (fits SQLite's
    # 64-bit integer). Everything else (abc, 0, 007, Bangla digits) is a 404.
    lookup_value_regex = r"[1-9][0-9]{0,17}"
    # PATCH (partial update) only; PUT is intentionally not supported.
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def filter_queryset(self, queryset):
        # Filters belong to the list only. Without this, GET /todos/5?status=pending
        # would 404 for a completed todo and DELETE /todos/5?status=pending would
        # silently refuse to delete it (get_object() also filters).
        if self.action != "list":
            return queryset
        return super().filter_queryset(queryset)