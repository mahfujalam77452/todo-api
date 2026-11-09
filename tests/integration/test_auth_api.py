import pytest

from tests.factories import UserFactory


@pytest.mark.django_db
def test_health_is_public(api_client):
    response = api_client.get("/api/health")

    assert response.status_code == 200
    assert response.data == {"status": "ok"}


@pytest.mark.django_db
def test_register_login_refresh_and_logout_flow(api_client):
    credentials = {
        "name": "New User",
        "email": "new@example.com",
        "password": "A-safe-password-123!",
    }

    register = api_client.post("/api/auth/register", credentials, format="json")
    assert register.status_code == 201
    assert register.data == {
        "id": register.data["id"],
        "name": "New User",
        "email": "new@example.com",
    }

    login = api_client.post(
        "/api/auth/login",
        {"email": "NEW@example.com", "password": credentials["password"]},
        format="json",
    )
    assert login.status_code == 200
    assert set(("access", "refresh", "user")) <= login.data.keys()
    assert login.data["user"]["email"] == "new@example.com"

    refresh = api_client.post(
        "/api/auth/token/refresh",
        {"refresh": login.data["refresh"]},
        format="json",
    )
    assert refresh.status_code == 200
    assert "access" in refresh.data
    assert "refresh" in refresh.data

    logout = api_client.post(
        "/api/auth/logout", {"refresh": refresh.data["refresh"]}, format="json"
    )
    assert logout.status_code == 204
    assert logout.content == b""

    rejected_refresh = api_client.post(
        "/api/auth/token/refresh",
        {"refresh": refresh.data["refresh"]},
        format="json",
    )
    assert rejected_refresh.status_code == 401
    assert rejected_refresh.data["code"] == 401


@pytest.mark.django_db
def test_duplicate_registration_and_invalid_login_use_api_error_shape(api_client):
    user = UserFactory(password="A-safe-password-123!")

    duplicate = api_client.post(
        "/api/auth/register",
        {"name": "Other", "email": user.email.upper(), "password": "A-safe-password-123!"},
        format="json",
    )
    assert duplicate.status_code == 400
    assert duplicate.data["code"] == 400
    assert "email" in duplicate.data["details"]

    invalid_login = api_client.post(
        "/api/auth/login",
        {"email": user.email, "password": "wrong-password"},
        format="json",
    )
    assert invalid_login.status_code == 401
    assert invalid_login.data["code"] == 401
    assert "error" in invalid_login.data
