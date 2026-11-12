import pytest

from teams.models import Membership
from tests.factories import TeamFactory, TodoFactory, UserFactory


def login(api_client, user):
    response = api_client.post(
        "/api/auth/login",
        {"email": user.email, "password": "A-safe-password-123!"},
        format="json",
    )
    assert response.status_code == 200, response.data
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")


@pytest.mark.django_db
def test_todo_response_uses_status_and_assignment_metadata(authenticated_client, user):
    response = authenticated_client.post(
        "/api/todos",
        {"title": "Unassigned task", "status": "in_progress"},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["status"] == "in_progress"
    assert response.data["is_completed"] is False
    assert response.data["assigner"]["id"] == user.pk
    assert response.data["assignee"] is None
    assert response.data["team"] is None
    assert response.data["assignment_status"] is None


@pytest.mark.django_db
def test_same_team_assignment_succeeds_and_scopes_todo_to_both_users(api_client):
    assigner = UserFactory(email="assigner@example.com")
    assignee = UserFactory(email="assignee@example.com")
    team = TeamFactory(name="Engineering")
    Membership.objects.create(user=assigner, team=team)
    Membership.objects.create(user=assignee, team=team)
    login(api_client, assigner)

    created = api_client.post(
        "/api/todos", {"title": "Review PR"}, format="json"
    )
    todo_id = created.data["id"]
    assigned = api_client.post(
        f"/api/todos/{todo_id}/assign",
        {"assignee_id": assignee.pk},
        format="json",
    )

    assert assigned.status_code == 200
    assert assigned.data["assignee"]["id"] == assignee.pk
    assert assigned.data["assignment_status"] == "pending"
    assert assigned.data["team"]["id"] == team.pk

    api_client.credentials()
    login(api_client, assignee)
    visible = api_client.get(f"/api/todos/{todo_id}")
    assert visible.status_code == 200
    assert visible.data["id"] == todo_id

    assigned_to_me = api_client.get("/api/todos?relation=assigned_to_me")
    assert assigned_to_me.data["count"] == 1
    assigned_by_me = api_client.get("/api/todos?relation=assigned_by_me")
    assert assigned_by_me.data["count"] == 0


@pytest.mark.django_db
def test_cross_team_assignment_is_forbidden(api_client):
    assigner = UserFactory(email="assigner@example.com")
    assignee = UserFactory(email="assignee@example.com")
    first_team = TeamFactory(name="Engineering")
    second_team = TeamFactory(name="Design")
    Membership.objects.create(user=assigner, team=first_team)
    Membership.objects.create(user=assignee, team=second_team)
    todo = TodoFactory(assigner=assigner)
    login(api_client, assigner)

    response = api_client.post(
        f"/api/todos/{todo.pk}/assign",
        {"assignee_id": assignee.pk},
        format="json",
    )

    assert response.status_code == 403
    todo.refresh_from_db()
    assert todo.assignee_id is None
    assert todo.assignment_status is None


@pytest.mark.django_db
def test_create_with_same_team_assignee_uses_assignment_flow(api_client):
    assigner = UserFactory(email="assigner@example.com")
    assignee = UserFactory(email="assignee@example.com")
    team = TeamFactory()
    Membership.objects.create(user=assigner, team=team)
    Membership.objects.create(user=assignee, team=team)
    login(api_client, assigner)

    response = api_client.post(
        "/api/todos",
        {"title": "Already assigned", "assignee_id": assignee.pk},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["assignee"]["id"] == assignee.pk
    assert response.data["assignment_status"] == "pending"


@pytest.mark.django_db
def test_self_assignment_is_accepted_without_pending_assignment(api_client):
    user = UserFactory(email="self@example.com")
    team = TeamFactory()
    Membership.objects.create(user=user, team=team)
    login(api_client, user)

    response = api_client.post(
        "/api/todos", {"title": "My task", "assignee_id": user.pk}, format="json"
    )

    assert response.status_code == 201
    assert response.data["assignment_status"] == "accepted"
    assert response.data["assignee"]["id"] == user.pk
