import pytest

from notifications.models import Notification
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


def assigned_todo(assigner, assignee):
    team = TeamFactory()
    Membership.objects.create(user=assigner, team=team)
    Membership.objects.create(user=assignee, team=team)
    todo = TodoFactory(assigner=assigner)
    todo.assignee = assignee
    todo.team = team
    todo.assignment_status = "pending"
    todo.save(update_fields=["assignee", "team", "assignment_status"])
    return todo


@pytest.mark.django_db
def test_assignee_can_accept_and_assigner_is_notified(api_client):
    assigner = UserFactory(email="assigner@example.com")
    assignee = UserFactory(email="assignee@example.com")
    todo = assigned_todo(assigner, assignee)
    login(api_client, assignee)

    response = api_client.post(f"/api/todos/{todo.pk}/accept", {}, format="json")

    assert response.status_code == 200
    assert response.data["assignment_status"] == "accepted"
    notification = Notification.objects.get(recipient=assigner)
    assert notification.type == Notification.Type.ACCEPTED
    assert notification.todo_id == todo.pk
    assert notification.link == f"/todos/{todo.pk}"


@pytest.mark.django_db
def test_assignee_can_reject_and_duplicate_response_conflicts(api_client):
    assigner = UserFactory(email="assigner@example.com")
    assignee = UserFactory(email="assignee@example.com")
    todo = assigned_todo(assigner, assignee)
    login(api_client, assignee)

    rejected = api_client.post(
        f"/api/todos/{todo.pk}/reject",
        {"reason": "I do not have access to this project."},
        format="json",
    )
    assert rejected.status_code == 200
    assert rejected.data["assignment_status"] == "rejected"
    assert Notification.objects.filter(
        recipient=assigner, type=Notification.Type.REJECTED
    ).count() == 1

    duplicate = api_client.post(f"/api/todos/{todo.pk}/accept", {}, format="json")
    assert duplicate.status_code == 409
    assert duplicate.data["code"] == 409


@pytest.mark.django_db
def test_assignee_can_edit_but_assigner_cannot_edit_assigned_todo(api_client):
    assigner = UserFactory(email="assigner@example.com")
    assignee = UserFactory(email="assignee@example.com")
    todo = assigned_todo(assigner, assignee)

    login(api_client, assigner)
    denied = api_client.patch(
        f"/api/todos/{todo.pk}", {"title": "No longer mine"}, format="json"
    )
    assert denied.status_code == 403

    api_client.credentials()
    login(api_client, assignee)
    allowed = api_client.patch(
        f"/api/todos/{todo.pk}", {"title": "Updated by assignee"}, format="json"
    )
    assert allowed.status_code == 200


@pytest.mark.django_db
def test_only_assigner_can_delete_and_unassigned_creator_can_edit(api_client):
    assigner = UserFactory(email="assigner@example.com")
    assignee = UserFactory(email="assignee@example.com")
    team = TeamFactory()
    Membership.objects.create(user=assigner, team=team)
    Membership.objects.create(user=assignee, team=team)
    todo = TodoFactory(assigner=assigner)

    login(api_client, assigner)
    updated = api_client.patch(
        f"/api/todos/{todo.pk}", {"title": "Still editable"}, format="json"
    )
    assert updated.status_code == 200

    assigned = api_client.post(
        f"/api/todos/{todo.pk}/assign", {"assignee_id": assignee.pk}, format="json"
    )
    assert assigned.status_code == 200
    denied_delete = api_client.delete(f"/api/todos/{todo.pk}")
    assert denied_delete.status_code == 204


@pytest.mark.django_db
def test_notification_api_is_private_and_supports_read_flows(api_client):
    recipient = UserFactory(email="recipient@example.com")
    other = UserFactory(email="other@example.com")
    todo = TodoFactory(assigner=other)
    Notification.objects.create(
        recipient=recipient,
        type=Notification.Type.ASSIGNED,
        message="A task",
        todo=todo,
        link=f"/todos/{todo.pk}",
    )
    Notification.objects.create(
        recipient=other,
        type=Notification.Type.ACCEPTED,
        message="Another task",
        todo=todo,
        link=f"/todos/{todo.pk}",
    )
    login(api_client, recipient)

    listing = api_client.get("/api/notifications?is_read=false")
    assert listing.status_code == 200
    assert listing.data["count"] == 1
    notification_id = listing.data["results"][0]["id"]

    unread = api_client.get("/api/notifications/unread-count")
    assert unread.data == {"count": 1}
    marked = api_client.post(f"/api/notifications/{notification_id}/read", {}, format="json")
    assert marked.status_code == 200
    assert marked.data["is_read"] is True
    assert api_client.get("/api/notifications/unread-count").data == {"count": 0}

    other_notification = Notification.objects.create(
        recipient=recipient,
        type=Notification.Type.REJECTED,
        message="Read all",
        todo=todo,
        link=f"/todos/{todo.pk}",
    )
    read_all = api_client.post("/api/notifications/read-all", {}, format="json")
    assert read_all.status_code == 200
    assert read_all.data == {"updated": 1}
    assert Notification.objects.get(pk=other_notification.pk).is_read is True

    api_client.credentials()
    assert api_client.get(f"/api/notifications/{notification_id}/read").status_code == 401
