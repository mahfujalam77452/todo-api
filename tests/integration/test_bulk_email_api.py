"""Mock tests for the PM bulk email API.

The Celery task is replaced by a mock, so no Redis, no worker and no real email
are needed: we only check what the API hands to the background task.
"""
from unittest.mock import patch

import pytest

from activity.models import BulkEmail
from teams.models import Membership
from tests.factories import TeamFactory, UserFactory
from tests.integration.test_phase2_api import login


@pytest.mark.django_db
def test_pm_bulk_email_is_queued_for_the_other_team_members(
    api_client, django_capture_on_commit_callbacks
):
    team = TeamFactory(name="Mock Team")
    pm, first, second = UserFactory(role="pm"), UserFactory(), UserFactory()
    outsider = UserFactory()
    for user in (pm, first, second):
        Membership.objects.create(user=user, team=team)
    Membership.objects.create(user=outsider, team=TeamFactory())
    login(api_client, pm)

    with patch("activity.views.send_bulk_email") as mock_task:
        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(
                "/api/pm/bulk-emails",
                {"subject": "Standup moved", "message": "Tomorrow at 10am."},
                format="json",
            )

    assert response.status_code == 202
    assert response.data["recipient_count"] == 2
    bulk = BulkEmail.objects.get()
    mock_task.delay.assert_called_once()
    bulk_id, recipient_ids = mock_task.delay.call_args.args
    assert bulk_id == bulk.pk
    # Only the other members of the PM's own team: not the PM, not another team.
    assert sorted(recipient_ids) == sorted([first.pk, second.pk])


@pytest.mark.django_db
def test_bulk_email_is_not_queued_when_the_request_is_refused(
    api_client, django_capture_on_commit_callbacks
):
    team = TeamFactory()
    pm, member = UserFactory(role="pm"), UserFactory()
    for user in (pm, member):
        Membership.objects.create(user=user, team=team)
    payload = {"subject": "Hello", "message": "Hi all"}

    with patch("activity.views.send_bulk_email") as mock_task:
        with django_capture_on_commit_callbacks(execute=True):
            login(api_client, member)
            forbidden = api_client.post("/api/pm/bulk-emails", payload, format="json")

            login(api_client, pm)
            invalid = api_client.post(
                "/api/pm/bulk-emails", {"subject": "", "message": "Hi all"}, format="json"
            )

    assert forbidden.status_code == 403  # a normal member is not a Project Manager
    assert invalid.status_code == 400  # the PM sent an empty subject
    mock_task.delay.assert_not_called()
    assert BulkEmail.objects.count() == 0