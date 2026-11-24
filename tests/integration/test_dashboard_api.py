from datetime import timedelta

import pytest
from django.utils import timezone

from teams.models import Membership
from scrums.models import Scrum
from todos.models import Todo
from dashboard.models import OverdueAlert
from tests.factories import (
    AdminUserFactory,
    CategoryFactory,
    TeamFactory,
    TodoFactory,
    UserFactory,
)


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


@pytest.mark.django_db
def test_scrum_history_filters_and_admin_bottlenecks(api_client):
    admin = AdminUserFactory(email="scrum-admin@example.com")
    member = UserFactory(email="scrum-member@example.com")
    team = TeamFactory(name="Scrum Team")
    Membership.objects.create(user=member, team=team)
    scrum = Scrum.objects.create(team=team, name="Sprint 1", status=Scrum.Status.ENDED)
    login(api_client, admin)

    start = api_client.post(f"/api/admin/scrums/{scrum.pk}/start", {}, format="json")
    assert start.status_code == 200
    todo = TodoFactory(assigner=member, team=team, scrum=scrum, priority=3)
    history = api_client.get(f"/api/admin/dashboard/history?scrum={scrum.pk}&category=")
    assert history.status_code == 200
    assert [row["id"] for row in history.data["todos"]] == [todo.pk]
    assert history.data["statistics"]["completed_high"] == 0

    unassigned = api_client.get("/api/admin/dashboard/bottlenecks/unassigned")
    assert unassigned.status_code == 200
    assert unassigned.data[0]["id"] == todo.pk

    settings = api_client.patch(
        "/api/admin/dashboard/settings",
        {"overloaded_user_threshold": 2},
        format="json",
    )
    assert settings.status_code == 200
    assert settings.data["overloaded_user_threshold"] == 2


@pytest.mark.django_db
def test_admin_scrum_lifecycle_generates_names_and_ends_scrum(api_client):
    admin = AdminUserFactory(email="scrum-lifecycle-admin@example.com")
    team = TeamFactory(name="Lifecycle Team")
    login(api_client, admin)

    first = api_client.post("/api/admin/scrums", {"team": team.pk}, format="json")
    second = api_client.post("/api/admin/scrums", {"team": team.pk, "name": "custom"}, format="json")
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.data["name"] == "scrum-1"
    assert second.data["name"] == "scrum-2"
    assert first.data["status"] == "created"
    assert second.data["status"] == "created"

    started = api_client.post(f"/api/admin/scrums/{first.data['id']}/start", {}, format="json")
    assert started.status_code == 200
    assert started.data["status"] == "running"
    ended = api_client.post(f"/api/admin/scrums/{first.data['id']}/end", {}, format="json")
    assert ended.status_code == 200
    assert ended.data["status"] == "ended"
    assert ended.data["ended_at"] is not None


@pytest.mark.django_db
def test_active_scrum_is_attached_to_new_and_existing_team_todos(api_client):
    admin = AdminUserFactory(email="scrum-association-admin@example.com")
    member = UserFactory(email="scrum-association-member@example.com")
    team = TeamFactory(name="Association Team")
    Membership.objects.create(user=member, team=team)
    backlog = TodoFactory(assigner=member, team=team)
    login(api_client, admin)

    created = api_client.post(
        "/api/admin/scrums", {"team": team.pk}, format="json"
    )
    started = api_client.post(
        f"/api/admin/scrums/{created.data['id']}/start", {}, format="json"
    )
    assert started.status_code == 200
    backlog.refresh_from_db()
    assert backlog.scrum_id == created.data["id"]

    member_token = api_client.post(
        "/api/auth/login",
        {"email": member.email, "password": "A-safe-password-123!"},
        format="json",
    ).data["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {member_token}")
    new_todo = api_client.post(
        "/api/todos", {"title": "Active Scrum task"}, format="json"
    )
    assert new_todo.status_code == 201
    assert new_todo.data["team"]["id"] == team.pk
    assert new_todo.data["scrum"]["id"] == created.data["id"]


@pytest.mark.django_db
def test_todo_history_combines_scrum_category_date_and_relation_filters(api_client):
    admin = AdminUserFactory(email="history-filter-admin@example.com")
    member = UserFactory(email="history-filter-member@example.com")
    team = TeamFactory(name="History Filter Team")
    category = CategoryFactory(name="History category")
    Membership.objects.create(user=member, team=team)
    scrum = Scrum.objects.create(team=team, name="scrum-1")
    login(api_client, admin)
    api_client.post(f"/api/admin/scrums/{scrum.pk}/start", {}, format="json")

    matching = TodoFactory(
        assigner=member, team=team, scrum=scrum, category=category
    )
    matching.assignee = member
    matching.assignment_status = "accepted"
    matching.save(update_fields=["assignee", "assignment_status"])
    excluded = TodoFactory(assigner=member, team=team, scrum=scrum)
    Todo.objects.filter(pk=excluded.pk).update(
        created_at=timezone.now() - timedelta(days=30)
    )

    response = api_client.get(
        f"/api/admin/dashboard/history?user={member.pk}"
        f"&scrum={scrum.pk}&category={category.pk}"
        f"&from={(timezone.now() - timedelta(days=1)).date()}&relation=assigned"
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.data["todos"]] == [matching.pk]


@pytest.mark.django_db
def test_user_performance_counts_only_tasks_assigned_to_selected_user(api_client):
    admin = AdminUserFactory(email="performance-admin@example.com")
    member = UserFactory(email="performance-member@example.com")
    other = UserFactory(email="performance-other@example.com")
    team = TeamFactory(name="Performance Team")
    Membership.objects.create(user=member, team=team)
    Membership.objects.create(user=other, team=team)
    scrum = Scrum.objects.create(team=team, name="scrum-1")
    login(api_client, admin)
    api_client.post(f"/api/admin/scrums/{scrum.pk}/start", {}, format="json")

    assigned = TodoFactory(
        assigner=other,
        team=team,
        scrum=scrum,
        status="completed",
        priority=3,
        due_date=timezone.now() + timedelta(days=1),
    )
    assigned.assignee = member
    assigned.assignment_status = "accepted"
    assigned.assigned_at = timezone.now() - timedelta(hours=2)
    assigned.responded_at = timezone.now() - timedelta(hours=1)
    assigned.save(update_fields=["assignee", "assignment_status", "assigned_at", "responded_at"])

    created_for_other = TodoFactory(
        assigner=member,
        team=team,
        scrum=scrum,
        status="completed",
    )
    created_for_other.assignee = other
    created_for_other.assignment_status = "accepted"
    created_for_other.save(update_fields=["assignee", "assignment_status"])

    response = api_client.get(f"/api/admin/dashboard/history?user={member.pk}")
    assert response.status_code == 200
    assert {item["id"] for item in response.data["todos"]} == {
        assigned.pk,
        created_for_other.pk,
    }
    assert response.data["statistics"]["completed"] == 1
    assert response.data["statistics"]["completed_high"] == 1
    assert response.data["statistics"]["accepted"] == 1
    assert response.data["statistics"]["completed_on_time"] == 1
    assert response.data["statistics"]["completed_overdue"] == 0


@pytest.mark.django_db
def test_high_rejection_bottleneck_returns_responsible_todos(api_client):
    admin = AdminUserFactory(email="rejection-admin@example.com")
    member = UserFactory(email="rejection-member@example.com")
    team = TeamFactory(name="Rejection Team")
    Membership.objects.create(user=member, team=team)
    scrum = Scrum.objects.create(team=team, name="scrum-1")
    login(api_client, admin)
    api_client.post(f"/api/admin/scrums/{scrum.pk}/start", {}, format="json")

    rejected = TodoFactory(assigner=admin, team=team, scrum=scrum)
    rejected.assignee = member
    rejected.assignment_status = "rejected"
    rejected.save(update_fields=["assignee", "assignment_status"])

    response = api_client.get("/api/admin/dashboard/bottlenecks/high-rejection")
    assert response.status_code == 200
    assert [item["id"] for item in response.data] == [rejected.pk]


@pytest.mark.django_db
def test_overloaded_and_inactive_bottlenecks_use_configured_activity_rules(api_client):
    admin = AdminUserFactory(email="load-admin@example.com")
    member = UserFactory(email="load-member@example.com")
    dormant = UserFactory(email="load-dormant@example.com")
    team = TeamFactory(name="Load Team")
    Membership.objects.create(user=member, team=team)
    Membership.objects.create(user=dormant, team=team)
    scrum = Scrum.objects.create(team=team, name="scrum-1")
    login(api_client, admin)
    api_client.post(f"/api/admin/scrums/{scrum.pk}/start", {}, format="json")
    api_client.patch(
        "/api/admin/dashboard/settings",
        {"overloaded_user_threshold": 1},
        format="json",
    )

    assigned_ids = []
    for _ in range(2):
        todo = TodoFactory(assigner=admin, team=team, scrum=scrum)
        todo.assignee = member
        todo.assignment_status = "accepted"
        todo.save(update_fields=["assignee", "assignment_status"])
        assigned_ids.append(todo.pk)

    overview = api_client.get("/api/admin/dashboard/overview")
    overloaded = next(
        item for item in overview.data["bottlenecks"]["overloaded_users"]
        if item["id"] == member.pk
    )
    assert overloaded["active_count"] == 2
    overloaded_todos = api_client.get("/api/admin/dashboard/bottlenecks/overloaded")
    assert {item["id"] for item in overloaded_todos.data} == set(assigned_ids)

    inactive_ids = {
        item["id"] for item in overview.data["bottlenecks"]["inactive_users"]
    }
    assert dormant.pk in inactive_ids
    assert member.pk not in inactive_ids


@pytest.mark.django_db
def test_dashboard_metrics_use_fourteen_day_window_and_deduplicate_alerts(api_client):
    admin = AdminUserFactory(email="period-admin@example.com")
    team = TeamFactory(name="Period Team")
    scrum = Scrum.objects.create(team=team, name="scrum-1")
    login(api_client, admin)
    api_client.post(f"/api/admin/scrums/{scrum.pk}/start", {}, format="json")

    old = TodoFactory(
        assigner=admin,
        team=team,
        scrum=scrum,
        due_date=timezone.now() - timedelta(days=2),
    )
    Todo.objects.filter(pk=old.pk).update(
        created_at=timezone.now() - timedelta(days=20),
    )
    recent = TodoFactory(
        assigner=admin,
        team=team,
        scrum=scrum,
        due_date=timezone.now() - timedelta(days=1),
    )

    first = api_client.get("/api/admin/dashboard/overview")
    second = api_client.get("/api/admin/dashboard/overview")
    assert first.data["todos"] == 1
    assert first.data["bottlenecks"]["overdue_alert"]["count"] == 1
    assert second.data["bottlenecks"]["overdue_alert"]["active"] is True
    assert OverdueAlert.objects.filter(scope_key="active-scrums").count() == 1
    assert recent.pk != old.pk


@pytest.mark.django_db
def test_heatmap_and_team_analytics_use_completion_dates(api_client):
    admin = AdminUserFactory(email="analytics-admin@example.com")
    team = TeamFactory(name="Analytics Team")
    scrum = Scrum.objects.create(team=team, name="scrum-1")
    login(api_client, admin)
    api_client.post(f"/api/admin/scrums/{scrum.pk}/start", {}, format="json")
    completed = TodoFactory(
        assigner=admin,
        team=team,
        scrum=scrum,
        status="completed",
    )

    heatmap = api_client.get("/api/admin/dashboard/heatmap")
    assert heatmap.status_code == 200
    assert len(heatmap.data) == 90
    assert sum(item["count"] for item in heatmap.data) == 1

    analytics = api_client.get(
        f"/api/admin/dashboard/teams/{team.pk}/analytics?scrum={scrum.pk}"
    )
    assert analytics.status_code == 200
    assert analytics.data["scrum"] == str(scrum.pk)


@pytest.mark.django_db
def test_bottleneck_details_use_fourteen_day_scope(api_client):
    admin = AdminUserFactory(email="bottleneck-period-admin@example.com")
    team = TeamFactory(name="Bottleneck Period Team")
    scrum = Scrum.objects.create(
        team=team,
        name="scrum-1",
        status=Scrum.Status.RUNNING,
    )
    login(api_client, admin)

    recent_overdue = TodoFactory(
        assigner=admin,
        team=team,
        scrum=scrum,
        status="in_progress",
        due_date=timezone.now() - timedelta(days=1),
    )
    old_overdue = TodoFactory(
        assigner=admin,
        team=team,
        scrum=scrum,
        status="in_progress",
        due_date=timezone.now() - timedelta(days=1),
    )
    Todo.objects.filter(pk=old_overdue.pk).update(
        created_at=timezone.now() - timedelta(days=20),
    )

    overview = api_client.get("/api/admin/dashboard/overview")
    detail = api_client.get("/api/admin/dashboard/bottlenecks/overdue")

    assert overview.status_code == 200
    assert detail.status_code == 200
    assert overview.data["bottlenecks"]["overdue_todos"] == 1
    assert {item["id"] for item in detail.data} == {recent_overdue.pk}


@pytest.mark.django_db
def test_heatmap_includes_completion_from_ended_scrum(api_client):
    admin = AdminUserFactory(email="ended-heatmap-admin@example.com")
    team = TeamFactory(name="Ended Heatmap Team")
    scrum = Scrum.objects.create(
        team=team,
        name="scrum-1",
        status=Scrum.Status.ENDED,
        started_at=timezone.now() - timedelta(days=10),
        ended_at=timezone.now() - timedelta(days=2),
    )
    login(api_client, admin)
    completed = TodoFactory(
        assigner=admin,
        team=team,
        scrum=scrum,
        status="completed",
    )

    heatmap = api_client.get("/api/admin/dashboard/heatmap")
    assert heatmap.status_code == 200
    assert completed.completed_at is not None
    assert sum(item["count"] for item in heatmap.data) == 1
    assert completed.pk


@pytest.mark.django_db
def test_team_analytics_is_limited_to_last_six_months(api_client):
    admin = AdminUserFactory(email="six-month-admin@example.com")
    team = TeamFactory(name="Six Month Team")
    scrum = Scrum.objects.create(team=team, name="scrum-1")
    login(api_client, admin)
    api_client.post(f"/api/admin/scrums/{scrum.pk}/start", {}, format="json")

    old = TodoFactory(assigner=admin, team=team, scrum=scrum)
    Todo.objects.filter(pk=old.pk).update(
        created_at=timezone.now() - timedelta(days=200)
    )
    recent = TodoFactory(assigner=admin, team=team, scrum=scrum)

    response = api_client.get(f"/api/admin/dashboard/teams/{team.pk}/analytics")
    assert response.status_code == 200
    assert sum(item["count"] for item in response.data["task_creation"]) == 1
    assert recent.pk != old.pk
