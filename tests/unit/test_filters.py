from datetime import datetime

import pytest
from django.http import QueryDict
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from todos.filters import TodoFilter
from todos.models import Todo
from core.filters import StrictOrderingFilter, StrictSearchFilter
from tests.factories import TodoFactory


@pytest.mark.django_db
def test_status_filter_selects_completed_and_pending():
    completed = TodoFactory(is_completed=True)
    pending = TodoFactory(is_completed=False)
    queryset = Todo.objects.all()

    assert list(TodoFilter(QueryDict("status=Completed"), queryset).qs) == [completed]
    assert list(TodoFilter(QueryDict("status=pending"), queryset).qs) == [pending]


@pytest.mark.django_db
@freeze_time("2026-06-01T12:00:00+06:00")
def test_overdue_filter_excludes_completed_and_missing_due_dates():
    utc = timezone.get_fixed_timezone(0)
    overdue = TodoFactory(due_date=datetime(2026, 5, 31, 12, 0, tzinfo=utc))
    TodoFactory(due_date=datetime(2026, 5, 31, 12, 0, tzinfo=utc), is_completed=True)
    TodoFactory(due_date=None)
    TodoFactory(due_date=datetime(2026, 6, 2, 12, 0, tzinfo=utc))

    result = TodoFilter(QueryDict("overdue=true"), Todo.objects.all()).qs

    assert list(result) == [overdue]


@pytest.mark.django_db
def test_filter_rejects_invalid_boolean():
    data = QueryDict("overdue=yes")
    filter_set = TodoFilter(data, Todo.objects.all())

    with pytest.raises(Exception):
        list(filter_set.qs)


@pytest.mark.django_db
def test_category_and_priority_filters_support_repeated_values():
    first_category = TodoFactory().category
    if first_category is None:
        from tests.factories import CategoryFactory

        first_category = CategoryFactory()
    second_category = CategoryFactory()
    first = TodoFactory(category=first_category, priority=Todo.Priority.LOW)
    second = TodoFactory(category=second_category, priority=Todo.Priority.HIGH)
    data = QueryDict(
        f"category={first_category.pk}&category={second_category.pk}&priority=1&priority=3"
    )

    assert set(TodoFilter(data, Todo.objects.all()).qs) == {first, second}


@pytest.mark.django_db
def test_filter_rejects_unknown_category_and_invalid_priority():
    missing_category = TodoFilter(QueryDict("category=999999"), Todo.objects.all())
    invalid_priority = TodoFilter(QueryDict("priority=9"), Todo.objects.all())

    with pytest.raises(Exception):
        list(missing_category.qs)
    with pytest.raises(Exception):
        list(invalid_priority.qs)


def test_ordering_filter_rejects_unknown_or_duplicate_fields():
    class View:
        ordering_fields = ["title", "priority"]
        ordering_expressions = {}

    backend = StrictOrderingFilter()
    request = APIRequestFactory().get("/api/todos?ordering=password")

    with pytest.raises(Exception):
        backend.get_terms(Request(request), View())

    request = APIRequestFactory().get("/api/todos?ordering=title,title")
    with pytest.raises(Exception):
        backend.get_terms(Request(request), View())


def test_search_filter_rejects_excessive_input():
    backend = StrictSearchFilter()
    request = APIRequestFactory().get("/api/todos?search=" + ("word " * 25))

    with pytest.raises(Exception):
        backend.get_search_terms(Request(request))
