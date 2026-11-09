from datetime import datetime

import pytest
from django.utils import timezone

from categories.models import Category
from todos.models import Todo
from tests.factories import CategoryFactory, TodoFactory, UserFactory


def todo_payload(**overrides):
    payload = {
        "title": "Buy groceries",
        "description": "Milk and rice",
        "priority": 3,
        "is_completed": False,
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_todos_require_authentication(api_client):
    response = api_client.get("/api/todos")

    assert response.status_code == 401
    assert response.data["code"] == 401
    assert "error" in response.data


@pytest.mark.django_db
def test_todo_crud_rejects_put_and_ignores_owner_fields(authenticated_client, user):
    create = authenticated_client.post("/api/todos", todo_payload(user=999999), format="json")
    assert create.status_code == 201
    todo_id = create.data["id"]
    assert Todo.objects.get(pk=todo_id).user_id == user.pk

    put = authenticated_client.put(
        f"/api/todos/{todo_id}", todo_payload(title="PUT"), format="json"
    )
    assert put.status_code == 405
    assert put.data["code"] == 405

    patch = authenticated_client.patch(
        f"/api/todos/{todo_id}",
        {"title": "Updated", "id": 999999, "user": 999999},
        format="json",
    )
    assert patch.status_code == 200
    assert patch.data["title"] == "Updated"
    assert patch.data["id"] == todo_id

    delete = authenticated_client.delete(f"/api/todos/{todo_id}")
    assert delete.status_code == 204
    assert delete.content == b""

    second_delete = authenticated_client.delete(f"/api/todos/{todo_id}")
    assert second_delete.status_code == 404


@pytest.mark.django_db
def test_todo_list_is_paginated_and_isolates_users(authenticated_client, user):
    own_first = TodoFactory(user=user, title="Own first")
    own_second = TodoFactory(user=user, title="Own second")
    other = UserFactory()
    TodoFactory(user=other, title="Private other todo")

    response = authenticated_client.get("/api/todos?limit=1&offset=0")

    assert response.status_code == 200
    assert response.data["count"] == 2
    assert response.data["limit"] == 1
    assert response.data["offset"] == 0
    assert len(response.data["results"]) == 1
    assert response.data["results"][0]["id"] in {own_first.pk, own_second.pk}
    assert all(item["title"] != "Private other todo" for item in response.data["results"])


@pytest.mark.django_db
def test_todo_filters_search_ordering_and_category_relation(authenticated_client, user):
    work = CategoryFactory(name="Work")
    TodoFactory(
        user=user,
        title="Zebra task",
        description="Buy milk",
        category=work,
        priority=3,
        is_completed=False,
    )
    TodoFactory(
        user=user,
        title="alpha task",
        description="Something else",
        priority=1,
        is_completed=True,
    )

    search = authenticated_client.get("/api/todos?search=milk")
    assert search.status_code == 200
    assert search.data["count"] == 1
    assert search.data["results"][0]["category_name"] == "Work"

    filtered = authenticated_client.get("/api/todos?status=pending&priority=3&has_category=true")
    assert filtered.status_code == 200
    assert filtered.data["count"] == 1

    ordered = authenticated_client.get("/api/todos?ordering=title")
    assert ordered.status_code == 200
    assert [item["title"] for item in ordered.data["results"]] == ["alpha task", "Zebra task"]


@pytest.mark.django_db
def test_other_users_todos_are_hidden_as_not_found(authenticated_client, user):
    other_todo = TodoFactory(user=UserFactory())

    response = authenticated_client.get(f"/api/todos/{other_todo.pk}")
    patch = authenticated_client.patch(
        f"/api/todos/{other_todo.pk}", {"title": "Leaked"}, format="json"
    )

    assert response.status_code == 404
    assert patch.status_code == 404
    assert response.data["code"] == 404
    assert "error" in response.data


@pytest.mark.django_db
def test_invalid_todo_input_and_unknown_api_url_return_json_errors(authenticated_client):
    invalid = authenticated_client.post(
        "/api/todos", {"title": "", "priority": 9, "is_completed": "yes"}, format="json"
    )
    assert invalid.status_code == 400
    assert invalid.data["code"] == 400
    assert {"title", "priority", "is_completed"} <= invalid.data["details"].keys()

    unknown = authenticated_client.get("/api/api-does-not-exist")
    assert unknown.status_code == 404
    assert unknown.data == {"error": "Not found.", "code": 404}


@pytest.mark.django_db
def test_category_delete_sets_existing_todo_category_to_null(authenticated_client, user):
    category = CategoryFactory()
    todo = TodoFactory(user=user, category=category)

    category.delete()
    todo.refresh_from_db()

    response = authenticated_client.get(f"/api/todos/{todo.pk}")
    assert response.status_code == 200
    assert response.data["category"] is None
    assert response.data["category_name"] is None
