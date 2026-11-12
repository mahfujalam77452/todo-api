import pytest

from teams.models import Membership
from tests.factories import AdminUserFactory, TeamFactory, UserFactory


@pytest.mark.django_db
def test_register_cannot_escalate_role(api_client):
    response = api_client.post(
        "/api/auth/register",
        {
            "name": "Regular User",
            "email": "regular@example.com",
            "password": "A-safe-password-123!",
            "role": "admin",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["role"] == "member"
    assert response.data["team"] is None


@pytest.mark.django_db
def test_me_and_team_member_list_are_scoped_to_the_users_team(api_client):
    user = UserFactory(email="member@example.com")
    team = TeamFactory(name="Engineering")
    Membership.objects.create(user=user, team=team)
    teammate = UserFactory(email="teammate@example.com")
    Membership.objects.create(user=teammate, team=team)
    other_team = TeamFactory(name="Design")
    other = UserFactory(email="other@example.com")
    Membership.objects.create(user=other, team=other_team)

    login = api_client.post(
        "/api/auth/login",
        {"email": user.email, "password": "A-safe-password-123!"},
        format="json",
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    me = api_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.data["role"] == "member"
    assert me.data["team"] == {"id": team.pk, "name": team.name}

    members = api_client.get(f"/api/teams/{team.pk}/members")
    assert members.status_code == 200
    assert {item["email"] for item in members.data} == {
        user.email,
        teammate.email,
    }

    forbidden = api_client.get(f"/api/teams/{other_team.pk}/members")
    assert forbidden.status_code == 403


@pytest.mark.django_db
def test_admin_can_list_and_update_users_but_member_cannot(api_client):
    admin = AdminUserFactory(email="workspace-admin@example.com")
    target = UserFactory(email="target@example.com")
    member = UserFactory(email="member@example.com")
    team = TeamFactory()

    login = api_client.post(
        "/api/auth/login",
        {"email": admin.email, "password": "A-safe-password-123!"},
        format="json",
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    listing = api_client.get("/api/admin/users")
    assert listing.status_code == 200
    assert listing.data["count"] == 3
    target_item = next(item for item in listing.data["results"] if item["id"] == target.pk)
    assert target_item["role"] == "member"
    assert target_item["created_count"] == 0

    updated = api_client.patch(
        f"/api/admin/users/{target.pk}",
        {"role": "admin", "team_id": team.pk},
        format="json",
    )
    assert updated.status_code == 200
    assert updated.data["role"] == "admin"
    assert updated.data["team"] == {"id": team.pk, "name": team.name}

    api_client.credentials()
    member_login = api_client.post(
        "/api/auth/login",
        {"email": member.email, "password": "A-safe-password-123!"},
        format="json",
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {member_login.data['access']}")
    forbidden = api_client.get("/api/admin/users")
    assert forbidden.status_code == 403


@pytest.mark.django_db
def test_admin_role_business_rules(api_client):
    admin = AdminUserFactory(email="first-admin@example.com")
    target = UserFactory(email="target@example.com")
    login = api_client.post(
        "/api/auth/login",
        {"email": admin.email, "password": "A-safe-password-123!"},
        format="json",
    )
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    self_change = api_client.patch(
        f"/api/admin/users/{admin.pk}", {"role": "member"}, format="json"
    )
    assert self_change.status_code == 403

    second_admin = AdminUserFactory(email="second-admin@example.com")
    demote = api_client.patch(
        f"/api/admin/users/{second_admin.pk}", {"role": "member"}, format="json"
    )
    assert demote.status_code == 200

    target_change = api_client.patch(
        f"/api/admin/users/{target.pk}", {"role": "admin"}, format="json"
    )
    assert target_change.status_code == 200


@pytest.mark.django_db
def test_admin_is_required_for_admin_user_api(api_client):
    assert api_client.get("/api/admin/users").status_code == 401
