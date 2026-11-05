from django_filters import rest_framework as filters
from rest_framework.exceptions import ValidationError

from categories.models import Category
from core.filters import parse_bool, parse_id

from .models import Todo

STATUS_CHOICES = [("completed", "completed"), ("pending", "pending")]
MAX_CATEGORY_FILTERS = 20


class TodoFilter(filters.FilterSet):
    """Query parameters accepted by GET /api/todos (besides search/ordering/limit/offset)."""

    status = filters.ChoiceFilter(
        choices=STATUS_CHOICES,
        method="filter_status",
        help_text="completed or pending",
    )
    category = filters.CharFilter(
        method="filter_category",
        help_text="Category id. Repeat for several: ?category=1&category=2",
    )
    has_category = filters.CharFilter(
        method="filter_has_category",
        help_text="true: only todos with a category, false: only todos without one",
    )

    class Meta:
        model = Todo
        fields = []  # only the explicitly declared filters above

    def __init__(self, data=None, *args, **kwargs):
        if data is not None:
            data = data.copy()
            # ?status=Completed and ?status=%20pending%20 are fine.
            if "status" in data:
                data["status"] = data["status"].strip().lower()
            # Blank values (?category=&category=3) are dropped before filtering.
            for key in ("category", "has_category"):
                if key in data:
                    values = [v.strip() for v in data.getlist(key) if v.strip()]
                    if values:
                        data.setlist(key, values)
                    else:
                        data.pop(key)
        super().__init__(data, *args, **kwargs)

    def filter_status(self, queryset, name, value):
        return queryset.filter(is_completed=(value == "completed"))

    def filter_category(self, queryset, name, value):
        # django-filter hands over only the last value; read all of them.
        ids = list(dict.fromkeys(parse_id(v, name) for v in self.data.getlist(name)))
        if len(ids) > MAX_CATEGORY_FILTERS:
            raise ValidationError(
                {name: [f"At most {MAX_CATEGORY_FILTERS} categories can be given."]}
            )
        existing = set(Category.objects.filter(pk__in=ids).values_list("pk", flat=True))
        missing = [i for i in ids if i not in existing]
        if missing:
            listed = ", ".join(map(str, missing))
            message = (
                f"Category {listed} does not exist."
                if len(missing) == 1
                else f"Categories {listed} do not exist."
            )
            raise ValidationError({name: [message]})
        return queryset.filter(category_id__in=ids)

    def filter_has_category(self, queryset, name, value):
        return queryset.filter(category__isnull=not parse_bool(value, name))