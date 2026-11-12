from datetime import timedelta

import pytest
from django.utils import timezone

from teams.models import Membership
from tests.factories import AdminUserFactory, TeamFactory, TodoFactory, UserFactory


def login(api_client, user):
    response = api_client.post(
        "/api/auth/login",
        {"email": user.email, "password": "A-safe-password-123!"},
        format="json",
    )
    assert response.status_code == 200, response.data
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")


@pytest.mark.django_db
def test_admin_dashboard_overview_users_teams_todos_and_bottlenecks(api_client):
    admin = AdminUserFactory(email="dashboard-admin@example.com")
    member = UserFactory(email="dashboard-member@example.com")
    team = TeamFactory(name="Engineering")
    Membership.objects.create(user=member, team=team)
    completed = TodoFactory(assigner=member, status="completed")
    pending = TodoFactory(assigner=member, status="pending")
    pending.assignee = admin
    pending.team = team
    pending.assignment_status = "pending"
    pending.assigned_at = timezone.now() - timedelta(days=8)
    pending.save(update_fields=["assignee", "team", "assignment_status", "assigned_at"])
    overdue = TodoFactory(
        assigner=member,
        status="in_progress",
        due_date=timezone.now() - timedelta(days=1),
    )
    login(api_client, admin)

    response = api_client.get("/api/admin/dashboard/overview")

    assert response.status_code == 200
    assert response.data["users"] == 2
    assert response.data["teams"] == 1
    assert response.data["todos"] == 3
    assert response.data["completed_todos"] == 1
    assert response.data["incomplete_todos"] == 2
    assert response.data["pending_assignments"] == 1
    assert response.data["completion_rate"] == 33.33
    assert response.data["bottlenecks"]["pending_assignments_over_7_days"] == 1
    assert response.data["bottlenecks"]["overdue_todos"] == 1
    assert completed.pk != overdue.pk


@pytest.mark.django_db
def test_dashboard_user_team_activity_and_read_only_todo_endpoints(api_client):
    admin = AdminUserFactory(email="dashboard-admin@example.com")
    member = UserFactory(email="dashboard-member@example.com")
    team = TeamFactory(name="Engineering")
    Membership.objects.create(user=member, team=team)
    todo = TodoFactory(assigner=member, status="completed")
    todo.assignee = member
    todo.team = team
    todo.assignment_status = "accepted"
    todo.assigned_at = timezone.now() - timedelta(hours=2)
    todo.responded_at = timezone.now() - timedelta(hours=1)
    todo.save(update_fields=["assignee", "team", "assignment_status", "assigned_at", "responded_at"])
    login(api_client, admin)

    users = api_client.get("/api/admin/dashboard/users")
    assert users.status_code == 200
    member_row = next(row for row in users.data if row["id"] == member.pk)
    assert member_row["created_count"] == 1
    assert member_row["assigned_count"] == 1
    assert member_row["completed_count"] == 1
    assert member_row["completion_rate"] == 100.0

    teams = api_client.get("/api/admin/dashboard/teams")
    assert teams.status_code == 200
    assert teams.data[0]["todo_count"] == 1
    assert teams.data[0]["completion_rate"] == 100.0

    activity = api_client.get("/api/admin/dashboard/activity?limit=2")
    assert activity.status_code == 200
    assert len(activity.data) == 2
    assert all(item["todo_id"] == todo.pk for item in activity.data)

    user_todos = api_client.get(f"/api/admin/users/{member.pk}/todos")
    assert user_todos.status_code == 200
    assert [item["id"] for item in user_todos.data] == [todo.pk]

    detail = api_client.get(f"/api/admin/todos/{todo.pk}")
    assert detail.status_code == 200
    assert detail.data["id"] == todo.pk

    assert api_client.post("/api/admin/dashboard/overview", {}, format="json").status_code == 405
    assert api_client.patch("/api/admin/dashboard/users", {}, format="json").status_code == 405
    assert api_client.delete(f"/api/admin/todos/{todo.pk}").status_code == 405


@pytest.mark.django_db
def test_dashboard_is_admin_only(api_client):
    member = UserFactory(email="dashboard-member@example.com")
    login(api_client, member)

    assert api_client.get("/api/admin/dashboard/overview").status_code == 403
    assert api_client.get("/api/admin/dashboard/users").status_code == 403
    assert api_client.get("/api/admin/dashboard/teams").status_code == 403
    assert api_client.get("/api/admin/dashboard/activity").status_code == 403
