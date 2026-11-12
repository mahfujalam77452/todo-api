from datetime import datetime

import pytest
from django.utils import timezone

from categories.models import Category
from todos.models import Todo
from tests.factories import CategoryFactory, TodoFactory, UserFactory


@pytest.mark.django_db
def test_deleting_category_sets_todo_category_to_null():
    category = CategoryFactory()
    todo = TodoFactory(category=category)

    category.delete()

    todo.refresh_from_db()
    assert todo.category_id is None


@pytest.mark.django_db
def test_deleting_user_cascades_to_owned_todos():
    user = UserFactory()
    todo = TodoFactory(assigner=user)
    todo_id = todo.pk

    user.delete()

    assert not Todo.objects.filter(pk=todo_id).exists()


@pytest.mark.django_db
def test_default_ordering_uses_id_as_tie_breaker():
    user = UserFactory()
    first = TodoFactory(assigner=user)
    second = TodoFactory(assigner=user)
    same_time = timezone.make_aware(datetime(2026, 1, 1, 12, 0))
    Todo.objects.filter(pk__in=[first.pk, second.pk]).update(created_at=same_time)

    assert list(Todo.objects.filter(assigner=user))[:2] == [second, first]


@pytest.mark.django_db
def test_todo_serializer_exposes_priority_display_and_category_name():
    category = CategoryFactory(name="Work")
    todo = TodoFactory(category=category, priority=Todo.Priority.HIGH)

    from todos.serializers import TodoSerializer

    data = TodoSerializer(todo).data

    assert data["priority_display"] == "High"
    assert data["category_name"] == "Work"
    assert "user" not in data
