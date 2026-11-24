import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from .models import ActivityLog
from .services import get_team_pm

logger = logging.getLogger("api.activity")

ACTION_VERB = {
    ActivityLog.Action.CREATED: "created",
    ActivityLog.Action.ASSIGNED: "assigned",
    ActivityLog.Action.ACCEPTED: "accepted",
    ActivityLog.Action.REJECTED: "rejected",
    ActivityLog.Action.UPDATED: "updated",
    ActivityLog.Action.DELETED: "deleted",
}


def build_action_context(log):
    changes = [
        {"field": field.replace("_", " ").title(), "old": old, "new": new}
        for field, (old, new) in (log.details.get("changes") or {}).items()
    ]
    link = None
    if log.todo_id and log.action != ActivityLog.Action.DELETED:
        link = f"{settings.FRONTEND_URL.rstrip('/')}/todos/{log.todo_id}"
    return {
        "log": log,
        "team": log.team,
        "verb": ACTION_VERB[log.action],
        "assignee": log.details.get("assignee"),
        "reason": log.details.get("reason"),
        "changes": changes,
        "link": link,
        "when": timezone.localtime(log.created_at),
    }


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def send_action_email(self, log_id):
    """Email one team action to the team's Project Manager."""
    try:
        log = ActivityLog.objects.select_related("team", "actor").get(pk=log_id)
    except ActivityLog.DoesNotExist:
        return "log not found"
    if log.pm_notified_at is not None:
        return "already sent"

    pm = get_team_pm(log.team_id)
    if pm is None:
        return "team has no project manager"
    # The PM's own actions are not mailed to the PM.
    if log.actor_id == pm.pk:
        return "actor is the project manager"

    context = build_action_context(log)
    context["pm"] = pm
    subject = f"[{log.team.name}] {log.actor_name} {context['verb']} todo: {log.todo_title}"
    subject = " ".join(subject.split())[:200]  # one line, no header injection

    message = EmailMultiAlternatives(
        subject=subject,
        body=render_to_string("activity/email/action.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[pm.email],
    )
    message.attach_alternative(render_to_string("activity/email/action.html", context), "text/html")
    message.send()

    # Only after a successful send; a failure above is retried.
    ActivityLog.objects.filter(pk=log.pk).update(pm_notified_at=timezone.now())
    return f"sent to {pm.email}"