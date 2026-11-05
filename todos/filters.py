from django_filters import rest_framework as filters

from .models import Todo

STATUS_CHOICES = [("completed", "completed"), ("pending", "pending")]


class TodoFilter(filters.FilterSet):
    """Query parameters accepted by GET /api/todos."""

    status = filters.ChoiceFilter(
        choices=STATUS_CHOICES,
        method="filter_status",
        help_text="completed or pending",
    )

    class Meta:
        model = Todo
        fields = []  # only the explicitly declared filters above

    def __init__(self, data=None, *args, **kwargs):
        # ?status=Completed and ?status=%20pending%20 are fine.
        if data is not None and "status" in data:
            data = data.copy()
            data["status"] = data["status"].strip().lower()
        super().__init__(data, *args, **kwargs)

    def filter_status(self, queryset, name, value):
        return queryset.filter(is_completed=(value == "completed"))