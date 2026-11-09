import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from rest_framework.test import APIRequestFactory

from categories.permissions import CategoryPermissions
from categories.views import CategoryViewSet
from tests.factories import StaffUserFactory, UserFactory


def category_request(method, user):
    request = APIRequestFactory().generic(method, "/api/categories")
    request.user = user
    return request


@pytest.mark.django_db
def test_authenticated_users_can_read_categories():
    permission = CategoryPermissions()
    user = UserFactory()

    assert permission.has_permission(category_request("GET", user), CategoryViewSet()) is True


@pytest.mark.django_db
def test_regular_users_cannot_modify_categories():
    permission = CategoryPermissions()
    user = UserFactory()

    assert permission.has_permission(category_request("POST", user), CategoryViewSet()) is False


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["PATCH", "DELETE"])
def test_regular_users_cannot_patch_or_delete_categories(method):
    permission = CategoryPermissions()
    user = UserFactory()

    assert permission.has_permission(category_request(method, user), CategoryViewSet()) is False


@pytest.mark.django_db
def test_anonymous_users_cannot_read_categories():
    permission = CategoryPermissions()
    request = category_request("GET", UserFactory())
    request.user = AnonymousUser()

    assert permission.has_permission(request, CategoryViewSet()) is False


@pytest.mark.django_db
def test_staff_users_need_the_model_permission_to_modify_categories():
    permission = CategoryPermissions()
    staff = StaffUserFactory()
    request = category_request("POST", staff)

    assert permission.has_permission(request, CategoryViewSet()) is False

    permission_object = Permission.objects.get(
        codename="add_category", content_type__app_label="categories"
    )
    staff.user_permissions.add(permission_object)
    request.user = get_user_model().objects.get(pk=staff.pk)

    assert permission.has_permission(request, CategoryViewSet()) is True
