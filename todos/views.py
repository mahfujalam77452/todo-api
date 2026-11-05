from rest_framework.viewsets import ModelViewSet

from .models import Todo
from .serializers import TodoSerializer


class TodoViewSet(ModelViewSet):
    # select_related: category_name is read for every row, so fetch it with the
    # todos in one query instead of one extra query per todo (N+1).
    # Ordering comes from Todo.Meta: newest first, id as the tie-breaker.
    queryset = Todo.objects.select_related("category")
    serializer_class = TodoSerializer
    # Plain ASCII digits, no leading zero, at most 18 digits (fits SQLite's
    # 64-bit integer). Everything else (abc, 0, 007, Bangla digits) is a 404.
    lookup_value_regex = r"[1-9][0-9]{0,17}"
    # Enabled task by task: POST (1.4), GET list (1.5), GET one (1.6),
    # PATCH (1.7), DELETE (1.8). PUT is never supported.
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]