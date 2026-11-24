"""Record team actions and tell the team's Project Manager about them."""
import logging

from django.db import transaction

from accounts.models import User
from teams.models import Membership

from .models import ActivityLog

logger = logging.getLogger("api.activity")

# Todo fields whose change is worth an email.
TRACKED_FIELDS = ("title", "description", "status", "priority", "due_date", "category_id")


def get_team_pm(team_id):
    return (
        User.objects.filter(role=User.Role.PM, is_active=True, membership__team_id=team_id)
        .only("id", "name", "email")
        .first()
    )


def record_activity(actor, action, todo, details=None):
    """Save the action and queue the email to the PM of the actor's team.

    Does nothing when the actor has no team. Call it inside the same
    transaction as the change itself: the log is saved or rolled back together
    with it, and the email is queued only after the commit.
    """
    membership = Membership.objects.filter(user=actor).only("team_id").first()
    if membership is None:
        return None

    log = ActivityLog.objects.create(
        team_id=membership.team_id,
        actor=actor,
        actor_name=actor.name,
        action=action,
        todo=todo,
        todo_title=todo.title,
        details=details or {},
    )

    from .tasks import send_action_email  # tasks.py imports this module too

    # robust=True: if Redis is down the error is logged and the API request
    # still succeeds. An action must never fail because of an email.
    transaction.on_commit(lambda: send_action_email.delay(log.pk), robust=True)
    return log


def snapshot_todo(todo):
    """Current values of the tracked fields (call BEFORE saving the update)."""
    return {field: getattr(todo, field) for field in TRACKED_FIELDS}


def diff_todo(before, todo):
    """{"status": ["pending", "completed"], ...} for the fields that changed."""
    changes = {}
    for field, old in before.items():
        new = getattr(todo, field)
        if old != new:
            key = "category" if field == "category_id" else field
            changes[key] = [_plain(old), _plain(new)]
    return changes


def _plain(value):
    # details is stored as JSON, so dates become ISO strings.
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value