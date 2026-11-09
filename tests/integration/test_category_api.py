import pytest

from tests.factories import CategoryFactory


@pytest.mark.django_db
def test_authenticated_users_can_read_cached_categories(authenticated_client):
    CategoryFactory(name="Work")

    first = authenticated_client.get("/api/categories")
    second = authenticated_client.get("/api/categories")

    assert first.status_code == 200
    assert first["X-Cache"] == "MISS"
    assert second.status_code == 200
    assert second["X-Cache"] == "HIT"
    assert second.data == first.data


@pytest.mark.django_db
def test_regular_user_cannot_modify_categories(authenticated_client):
    response = authenticated_client.post("/api/categories", {"name": "Work"}, format="json")

    assert response.status_code == 403
    assert response.data["code"] == 403


@pytest.mark.django_db
def test_admin_can_create_patch_and_delete_category(admin_client):
    created = admin_client.post("/api/categories", {"name": " Work "}, format="json")
    assert created.status_code == 201
    category_id = created.data["id"]
    assert created.data["name"] == "Work"

    patched = admin_client.patch(
        f"/api/categories/{category_id}", {"name": "Personal"}, format="json"
    )
    assert patched.status_code == 200
    assert patched.data["name"] == "Personal"

    deleted = admin_client.delete(f"/api/categories/{category_id}")
    assert deleted.status_code == 204


@pytest.mark.django_db
def test_category_put_is_not_allowed_and_duplicate_name_is_rejected(admin_client):
    category = CategoryFactory(name="Work")

    put = admin_client.put(
        f"/api/categories/{category.pk}", {"name": "Changed"}, format="json"
    )
    duplicate = admin_client.post("/api/categories", {"name": "work"}, format="json")

    assert put.status_code == 405
    assert put.data["code"] == 405
    assert duplicate.status_code == 400
    assert duplicate.data["code"] == 400
