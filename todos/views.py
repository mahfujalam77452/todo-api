from django.db.models import F
from django.db.models.functions import Lower
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.viewsets import ModelViewSet

from core.filters import StrictOrderingFilter, StrictSearchFilter

from .filters import TodoFilter
from .models import Todo
from .serializers import TodoSerializer


def _title_ci(descending):
    # Case-insensitive: SQLite's default sorts "Zebra" before "apple".
    return Lower("title").desc() if descending else Lower("title").asc()


def _nulls_last(field):
    # Todos without a due date go to the end in both directions.
    def build(descending):
        return F(field).desc(nulls_last=True) if descending else F(field).asc(nulls_last=True)

    return build


class TodoViewSet(ModelViewSet):
    # select_related: category_name is read for every row, so fetch it with the
    # todos in one query instead of one extra query per todo (N+1).
    # Ordering comes from Todo.Meta: newest first, id as the tie-breaker.
    queryset = Todo.objects.select_related("category")
    serializer_class = TodoSerializer
    # Plain ASCII digits, no leading zero, at most 18 digits (fits SQLite's
    # 64-bit integer). Everything else (abc, 0, 007, Bangla digits) is a 404.
    lookup_value_regex = r"[1-9][0-9]{0,17}"
    # PATCH (partial update) only; PUT is intentionally not supported.
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    # --- list query parameters: ?status= &category= &has_category= &search= &ordering=
    filter_backends = [DjangoFilterBackend, StrictSearchFilter, StrictOrderingFilter]
    filterset_class = TodoFilter
    search_fields = ["title", "description", "category__name"]
    ordering_fields = ["created_at", "title", "priority", "due_date"]
    ordering_expressions = {
        "title": _title_ci,
        "due_date": _nulls_last("due_date"),
    }

    def filter_queryset(self, queryset):
        # Filters belong to the list only. Without this, GET /todos/5?status=pending
        # would 404 for a completed todo and DELETE /todos/5?status=pending would
        # silently refuse to delete it (get_object() also filters).
        if self.action != "list":
            return queryset
        return super().filter_queryset(queryset)