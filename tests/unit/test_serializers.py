import pytest
from django.db import IntegrityError
from django.utils import timezone

from categories.models import Category
from categories.serializers import CategorySerializer
from todos.models import Todo
from todos.serializers import TodoSerializer
from tests.factories import CategoryFactory, TodoFactory


def serializer_errors(serializer):
    assert serializer.is_valid() is False
    return serializer.errors


@pytest.mark.django_db
@pytest.mark.parametrize("title", ["A", "x" * 255, "বাংলা 😊"])
def test_todo_title_accepts_boundaries_and_unicode(title):
    serializer = TodoSerializer(data={"title": title})

    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
@pytest.mark.parametrize("title", ["", " " * 4, "x" * 256, 123, [], {}, True, "\u200b", "\x00"])
def test_todo_title_rejects_blank_invalid_or_oversized_values(title):
    errors = serializer_errors(TodoSerializer(data={"title": title}))

    assert "title" in errors


@pytest.mark.django_db
@pytest.mark.parametrize("priority", [0, 4, "2", True])
def test_todo_priority_accepts_only_integer_choices(priority):
    errors = serializer_errors(TodoSerializer(data={"title": "Task", "priority": priority}))

    assert "priority" in errors


@pytest.mark.django_db
@pytest.mark.parametrize("priority", [1, 2, 3])
def test_todo_priority_accepts_each_choice(priority):
    serializer = TodoSerializer(data={"title": "Task", "priority": priority})

    assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
@pytest.mark.parametrize(
    "due_date",
    ["1999-12-31T23:59:59+06:00", "2100-01-01T00:00:00+06:00", "2026-02-30T10:00:00+06:00", "tomorrow"],
)
def test_due_date_rejects_invalid_or_out_of_range_values(due_date):
    errors = serializer_errors(TodoSerializer(data={"title": "Task", "due_date": due_date}))

    assert "due_date" in errors


@pytest.mark.django_db
def test_due_date_accepts_timezone_aware_iso_datetime():
    serializer = TodoSerializer(
        data={"title": "Task", "due_date": "2026-12-01T18:00:00+06:00"}
    )

    assert serializer.is_valid(), serializer.errors
    assert timezone.is_aware(serializer.validated_data["due_date"])


@pytest.mark.django_db
def test_due_date_accepts_naive_datetime_in_project_timezone():
    serializer = TodoSerializer(
        data={"title": "Task", "due_date": "2026-12-01T18:00:00"}
    )

    assert serializer.is_valid(), serializer.errors
    assert timezone.is_aware(serializer.validated_data["due_date"])


@pytest.mark.django_db
def test_due_date_can_be_cleared_with_null():
    todo = TodoFactory(due_date=timezone.now())
    serializer = TodoSerializer(todo, data={"due_date": None}, partial=True)

    assert serializer.is_valid(), serializer.errors
    serializer.save()

    assert Todo.objects.get(pk=todo.pk).due_date is None


@pytest.mark.django_db
def test_todo_defaults_priority_and_completion():
    serializer = TodoSerializer(data={"title": "Task"})

    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["priority"] == Todo.Priority.MEDIUM
    assert serializer.validated_data["status"] == Todo.Status.PENDING


@pytest.mark.django_db
def test_todo_rejects_invalid_status_values():
    for value in (None, "unknown", "COMPLETED", 1):
        errors = serializer_errors(
            TodoSerializer(data={"title": "Task", "status": value})
        )
        assert "status" in errors


@pytest.mark.django_db
def test_todo_ignores_read_only_and_owner_fields():
    owner = TodoFactory().assigner
    serializer = TodoSerializer(
        data={
            "title": "Task",
            "id": 999999,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "assigner": owner.pk,
        }
    )

    assert serializer.is_valid(), serializer.errors
    assert "id" not in serializer.validated_data
    assert "created_at" not in serializer.validated_data
    assert "updated_at" not in serializer.validated_data
    assert "assigner" not in serializer.validated_data


@pytest.mark.django_db
def test_same_todo_title_is_allowed_for_same_user():
    owner = TodoFactory().assigner
    first = TodoFactory(assigner=owner, title="Same title")
    second = TodoFactory(assigner=owner, title="Same title")

    assert first.pk != second.pk


@pytest.mark.django_db
def test_category_name_is_case_insensitive_and_trimmed():
    CategoryFactory(name=" Work ")
    serializer = CategorySerializer(data={"name": "work"})

    errors = serializer_errors(serializer)

    assert errors["name"][0] == "A category with this name already exists."


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["", " " * 3, "x" * 51, "\x00"])
def test_category_name_rejects_invalid_values(name):
    errors = serializer_errors(CategorySerializer(data={"name": name}))

    assert "name" in errors


@pytest.mark.django_db
def test_todo_can_use_and_clear_a_category():
    category = CategoryFactory()
    todo = TodoFactory()
    serializer = TodoSerializer(todo, data={"category": category.pk}, partial=True)

    assert serializer.is_valid(), serializer.errors
    serializer.save()
    assert Todo.objects.get(pk=todo.pk).category_id == category.pk

    serializer = TodoSerializer(todo, data={"category": None}, partial=True)
    assert serializer.is_valid(), serializer.errors
    serializer.save()
    assert Todo.objects.get(pk=todo.pk).category_id is None


@pytest.mark.django_db
def test_category_database_constraint_rejects_case_only_duplicate():
    CategoryFactory(name="Work")

    with pytest.raises(IntegrityError):
        Category.objects.create(name="work")


@pytest.mark.django_db
def test_patch_serializer_keeps_unchanged_todo_fields():
    todo = TodoFactory(title="Original", description="Details", priority=Todo.Priority.HIGH)
    serializer = TodoSerializer(todo, data={"title": "Updated"}, partial=True)

    assert serializer.is_valid(), serializer.errors
    updated = serializer.save()

    assert updated.title == "Updated"
    assert updated.description == "Details"
    assert updated.priority == Todo.Priority.HIGH
