import pytest

from teams.models import Membership
from tests.factories import TeamFactory, UserFactory


def _patch(admin_client, user, **body):
    return admin_client.patch(f"/api/admin/users/{user.pk}", body, format="json")


@pytest.mark.django_db
def test_admin_can_make_team_member_a_pm(admin_client):
    team = TeamFactory()
    user = UserFactory()
    Membership.objects.create(user=user, team=team)
    response = _patch(admin_client, user, role="pm")
    assert response.status_code == 200, response.data
    assert response.data["role"] == "pm"


@pytest.mark.django_db
def test_pm_needs_a_team(admin_client):
    user = UserFactory()
    assert _patch(admin_client, user, role="pm").status_code == 409


@pytest.mark.django_db
def test_second_pm_in_same_team_is_rejected(admin_client):
    team = TeamFactory()
    first, second = UserFactory(role="pm"), UserFactory()
    Membership.objects.create(user=first, team=team)
    Membership.objects.create(user=second, team=team)
    response = _patch(admin_client, second, role="pm")
    assert response.status_code == 409
    assert "already has a Project Manager" in response.data["error"]


@pytest.mark.django_db
def test_pm_cannot_be_moved_into_team_that_has_a_pm(admin_client):
    team_a, team_b = TeamFactory(), TeamFactory()
    pm_a, pm_b = UserFactory(role="pm"), UserFactory(role="pm")
    Membership.objects.create(user=pm_a, team=team_a)
    Membership.objects.create(user=pm_b, team=team_b)
    assert _patch(admin_client, pm_a, team_id=team_b.pk).status_code == 409


@pytest.mark.django_db
def test_pm_in_other_team_is_allowed_and_role_can_be_replaced(admin_client):
    team_a, team_b = TeamFactory(), TeamFactory()
    pm_a, member_b = UserFactory(role="pm"), UserFactory()
    Membership.objects.create(user=pm_a, team=team_a)
    Membership.objects.create(user=member_b, team=team_b)
    assert _patch(admin_client, member_b, role="pm").status_code == 200
    assert _patch(admin_client, pm_a, role="member").status_code == 200


@pytest.mark.django_db
def test_invalid_role_is_rejected(admin_client):
    user = UserFactory()
    assert _patch(admin_client, user, role="boss").status_code == 400