from django.db.models import Q
from django.utils import timezone
from django_filters import rest_framework as filters
from rest_framework.exceptions import ValidationError

from categories.models import Category
from core.filters import parse_bool, parse_datetime_param, parse_id

from .models import Todo
from .serializers import DUE_DATE_MAX_YEAR, DUE_DATE_MIN_YEAR

STATUS_CHOICES = [
    ("pending", "pending"),
    ("in_progress", "in_progress"),
    ("completed", "completed"),
]
ASSIGNMENT_STATUS_CHOICES = [
    ("pending", "pending"),
    ("accepted", "accepted"),
    ("rejected", "rejected"),
]
RELATION_CHOICES = [
    ("assigned_to_me", "assigned_to_me"),
    ("assigned_by_me", "assigned_by_me"),
]
MAX_CATEGORY_FILTERS = 20


class TodoFilter(filters.FilterSet):
    """Query parameters accepted by GET /api/todos (besides search/ordering/limit/offset)."""

    status = filters.ChoiceFilter(
        choices=STATUS_CHOICES,
        method="filter_status",
        help_text="pending, in_progress, or completed",
    )
    assignment_status = filters.ChoiceFilter(
        choices=ASSIGNMENT_STATUS_CHOICES,
        method="filter_assignment_status",
        help_text="pending, accepted, or rejected",
    )
    relation = filters.ChoiceFilter(
        choices=RELATION_CHOICES,
        method="filter_relation",
        help_text="assigned_to_me or assigned_by_me",
    )
    category = filters.CharFilter(
        method="filter_category",
        help_text="Category id. Repeat for several: ?category=1&category=2",
    )
    has_category = filters.CharFilter(
        method="filter_has_category",
        help_text="true: only todos with a category, false: only todos without one",
    )
    priority = filters.CharFilter(
        method="filter_priority",
        help_text="1 (low), 2 (medium) or 3 (high). Repeat for several: ?priority=2&priority=3",
    )
    overdue = filters.CharFilter(
        method="filter_overdue",
        help_text="true: not completed and past its due date; false: everything else",
    )
    due_before = filters.CharFilter(
        method="filter_due_before",
        help_text="due on or before this date and time, e.g. 2026-12-01T18:00:00+06:00",
    )
    due_after = filters.CharFilter(
        method="filter_due_after",
        help_text="due on or after this date and time, e.g. 2026-12-01T18:00:00+06:00",
    )
    team = filters.CharFilter(
        method="filter_team",
        help_text="Team id.",
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
            for key in ("category", "has_category", "priority", "overdue", "due_before", "due_after"):
                if key in data:
                    values = [v.strip() for v in data.getlist(key) if v.strip()]
                    if values:
                        data.setlist(key, values)
                    else:
                        data.pop(key)
        super().__init__(data, *args, **kwargs)

    def filter_status(self, queryset, name, value):
        return queryset.filter(status=value)

    def filter_assignment_status(self, queryset, name, value):
        return queryset.filter(assignment_status=value)

    def filter_relation(self, queryset, name, value):
        user = getattr(self.request, "user", None)
        if value == "assigned_to_me":
            return queryset.filter(assignee=user)
        return queryset.filter(assigner=user)

    def filter_team(self, queryset, name, value):
        return queryset.filter(team_id=parse_id(value, name))

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

    def filter_priority(self, queryset, name, value):
        allowed = {str(number): number for number, _ in Todo.Priority.choices}
        chosen = []
        for raw in self.data.getlist(name):
            if raw.strip() not in allowed:  # exact text: "01", "٣", "2.0" are all refused
                labels = ", ".join(f"{n} ({label})" for n, label in Todo.Priority.choices)
                raise ValidationError(
                    {name: [f"priority must be one of: {labels}. "
                            f"To pass several, repeat the parameter: ?priority=2&priority=3."]}
                )
            chosen.append(allowed[raw.strip()])
        return queryset.filter(priority__in=chosen)

    def filter_overdue(self, queryset, name, value):
        overdue = parse_bool(value, name)
        # Past due and still open. A todo without a due date is never overdue, and
        # exactly "now" is not yet overdue. `now` is read per request.
        condition = ~Q(status="completed") & Q(due_date__lt=timezone.now())
        return queryset.filter(condition) if overdue else queryset.exclude(condition)

    def _due(self, name, value):
        return parse_datetime_param(
            value, name, min_year=DUE_DATE_MIN_YEAR, max_year=DUE_DATE_MAX_YEAR
        )

    def filter_due_before(self, queryset, name, value):
        return queryset.filter(due_date__lte=self._due(name, value))

    def filter_due_after(self, queryset, name, value):
        return queryset.filter(due_date__gte=self._due(name, value))