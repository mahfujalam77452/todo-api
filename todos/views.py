from rest_framework.viewsets import ModelViewSet

from .models import Todo
from .serializers import TodoSerializer


class TodoViewSet(ModelViewSet):
    queryset = Todo.objects.select_related("category")
    serializer_class = TodoSerializer
    lookup_value_regex = r"\d{1,18}"  # see CategoryViewSet
    # Enabled task by task: POST (1.4), GET list (1.5), GET one (1.6),
    # PATCH (1.7), DELETE (1.8). PUT is never supported.
    http_method_names = ["post", "options"]