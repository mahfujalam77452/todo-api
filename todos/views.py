from rest_framework.exceptions import MethodNotAllowed
from rest_framework.viewsets import ModelViewSet

from .models import Todo
from .serializers import TodoSerializer


class TodoViewSet(ModelViewSet):
    # select_related: category_name is read for every row, so fetch it with the
    # todos in one query instead of one extra query per todo (N+1).
    # Ordering comes from Todo.Meta: newest first, id as the tie-breaker.
    queryset = Todo.objects.select_related("category")
    serializer_class = TodoSerializer
    lookup_value_regex = r"\d{1,18}"  # see CategoryViewSet
    # Enabled task by task: POST (1.4), GET list (1.5), GET one (1.6),
    # PATCH (1.7), DELETE (1.8). PUT is never supported.
    http_method_names = ["get", "post", "head", "options"]

    def retrieve(self, request, *args, **kwargs):
        # TEMP (Task 1.5): "get" also switches on GET /todos/{id}; keep it
        # closed until Task 1.6, which deletes this method.
        raise MethodNotAllowed(request.method)