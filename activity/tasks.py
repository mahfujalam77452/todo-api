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

@shared_task
def send_bulk_email(bulk_email_id, recipient_ids):
    """Send one PM message to every listed team member.

    Each person gets their own email, so nobody sees the other addresses.
    One bad address does not stop the others; failures are only counted.
    """
    from django.core.mail import get_connection

    from accounts.models import User
    from .models import BulkEmail

    try:
        bulk = BulkEmail.objects.select_related("team", "sender").get(pk=bulk_email_id)
    except BulkEmail.DoesNotExist:
        return "bulk email not found"
    if bulk.sent_at is not None:
        return "already sent"

    sender_email = bulk.sender.email if bulk.sender else None
    recipients = User.objects.filter(pk__in=recipient_ids, is_active=True).only("name", "email")
    subject = " ".join(f"[{bulk.team.name}] {bulk.subject}".split())[:200]

    sent = failed = 0
    with get_connection() as connection:
        for person in recipients:
            context = {"bulk": bulk, "team": bulk.team, "person": person}
            message = EmailMultiAlternatives(
                subject=subject,
                body=render_to_string("activity/email/bulk.txt", context),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[person.email],
                # Replies go to the PM, not to the no-reply address.
                reply_to=[sender_email] if sender_email else None,
                connection=connection,
            )
            message.attach_alternative(
                render_to_string("activity/email/bulk.html", context), "text/html"
            )
            try:
                message.send()
                sent += 1
            except Exception:
                failed += 1
                logger.exception("Bulk email %s failed for user %s", bulk.pk, person.pk)

    BulkEmail.objects.filter(pk=bulk.pk).update(
        sent_count=sent, failed_count=failed, sent_at=timezone.now()
    )
    return f"sent={sent} failed={failed}"


# ------------------------------------------------------------ daily PDF summary
@shared_task
def send_daily_team_summaries(report_date=None):
    """Run by Celery Beat at 00:00 (Asia/Dhaka): queue one summary per team.

    The report covers the day that just ended. One task per team, so a problem
    in one team never blocks the others.
    """
    from datetime import date, timedelta

    from .reports import teams_with_pm

    day = date.fromisoformat(report_date) if report_date else timezone.localdate() - timedelta(days=1)
    team_ids = teams_with_pm()
    for team_id in team_ids:
        send_team_summary.delay(team_id, day.isoformat())
    return f"queued {len(team_ids)} team summaries for {day.isoformat()}"


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def send_team_summary(self, team_id, report_date, force=False):
    """Build the PDF summary of one team for one day and mail it to the team's PM."""
    from datetime import date

    from django.template.defaultfilters import slugify

    from teams.models import Team

    from .models import DailySummary
    from .pdf import render_summary_pdf
    from .reports import build_team_summary

    day = date.fromisoformat(report_date)
    try:
        team = Team.objects.get(pk=team_id)
    except Team.DoesNotExist:
        return "team not found"

    pm = get_team_pm(team_id)
    if pm is None:
        return "team has no project manager"

    record, _ = DailySummary.objects.get_or_create(team=team, report_date=day)
    if record.sent_at is not None and not force:
        return "already sent"

    summary = build_team_summary(team, day)
    pdf_bytes = render_summary_pdf(summary)
    filename = f"team-summary-{slugify(team.name) or team.pk}-{day.isoformat()}.pdf"

    stats, snap = summary["day_stats"], summary["snapshot"]
    body = (
        f"Hi {pm.name},\n\n"
        f"Here is the daily summary of team \"{team.name}\" for {day:%A, %d %B %Y}.\n\n"
        + "\n".join(f"  - {line}" for line in summary["highlights"])
        + f"\n\nThe day: {stats['total']} actions, {stats['created']} todos created, "
        f"{stats['completed']} completed, {stats['accepted']} accepted, {stats['rejected']} rejected."
        f"\nNow: {snap['active']} active todos, {snap['overdue']} overdue, "
        f"{snap['awaiting']} awaiting an answer.\n\n"
        "The full report (member overview and timeline) is attached as a PDF.\n\n"
        "-- \nTodo Workspace (automatic message)\n"
    )
    message = EmailMultiAlternatives(
        subject=f"[{team.name}] Daily summary - {day:%d %b %Y}",
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[pm.email],
    )
    message.attach(filename, pdf_bytes, "application/pdf")
    message.send()

    record.sent_to = pm.email
    record.sent_at = timezone.now()
    record.save(update_fields=["sent_to", "sent_at"])
    _save_report_copy(filename, pdf_bytes)
    return f"sent {filename} to {pm.email}"


def _save_report_copy(filename, pdf_bytes):
    """Keep a copy on disk when REPORTS_DIR is set. Never fails the task."""
    if not settings.REPORTS_DIR:
        return
    try:
        from pathlib import Path

        folder = Path(settings.REPORTS_DIR)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / filename).write_bytes(pdf_bytes)
    except OSError:
        logger.warning("Could not save a copy of %s", filename, exc_info=True)