import pytest

from teams.models import Team


@pytest.mark.django_db
def test_unauthenticated_and_regular_users_cannot_create_teams(
    api_client, authenticated_client
):
    payload = {"name": "Engineering"}

    regular_user = authenticated_client.post("/api/admin/teams", payload, format="json")
    api_client.credentials()
    unauthenticated = api_client.post("/api/admin/teams", payload, format="json")

    assert unauthenticated.status_code == 401
    assert regular_user.status_code == 403


@pytest.mark.django_db
def test_admin_can_create_rename_and_delete_teams(admin_client):
    created = admin_client.post(
        "/api/admin/teams", {"name": " Engineering "}, format="json"
    )

    assert created.status_code == 201
    assert created.data["name"] == "Engineering"

    team_id = created.data["id"]
    renamed = admin_client.patch(
        f"/api/admin/teams/{team_id}", {"name": "Platform"}, format="json"
    )
    deleted = admin_client.delete(f"/api/admin/teams/{team_id}")

    assert renamed.status_code == 200
    assert renamed.data["name"] == "Platform"
    assert deleted.status_code == 204
    assert not Team.objects.filter(pk=team_id).exists()


@pytest.mark.django_db
def test_admin_team_endpoints_reject_put_and_duplicate_names(admin_client):
    first = Team.objects.create(name="Engineering")
    second = Team.objects.create(name="Support")

    put = admin_client.put(
        f"/api/admin/teams/{first.pk}", {"name": "Platform"}, format="json"
    )
    duplicate = admin_client.post(
        "/api/admin/teams", {"name": " engineering "}, format="json"
    )
    missing = admin_client.patch(
        f"/api/admin/teams/{second.pk}", {"name": "Engineering"}, format="json"
    )

    assert put.status_code == 405
    assert put.data["code"] == 405
    assert duplicate.status_code == 400
    assert duplicate.data["code"] == 400
    assert missing.status_code == 400
    assert missing.data["code"] == 400
