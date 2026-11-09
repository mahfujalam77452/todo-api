import pytest
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

from tests.factories import UserFactory


@pytest.fixture(autouse=True)
def clear_cache():
    cache_settings = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "todo-api-integration-tests",
        }
    }
    with override_settings(CACHES=cache_settings):
        cache.clear()
        yield
        cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    user = UserFactory()
    user.set_password("A-safe-password-123!")
    user.save(update_fields=["password"])
    return user


@pytest.fixture
def authenticated_client(api_client, user):
    response = api_client.post(
        "/api/auth/login",
        {"email": user.email, "password": "A-safe-password-123!"},
        format="json",
    )
    assert response.status_code == 200, response.data
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return api_client


@pytest.fixture
def admin_user():
    user = UserFactory(
        email="admin@example.com",
        is_staff=True,
        is_superuser=True,
    )
    user.set_password("A-safe-password-123!")
    user.save(update_fields=["password"])
    return user


@pytest.fixture
def admin_client(api_client, admin_user):
    response = api_client.post(
        "/api/auth/login",
        {"email": admin_user.email, "password": "A-safe-password-123!"},
        format="json",
    )
    assert response.status_code == 200, response.data
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
    return api_client
