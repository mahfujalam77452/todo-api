"""Collect the numbers for one team's daily summary (no PDF code here)."""
from collections import Counter
from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from accounts.models import User
from teams.models import Membership
from todos.models import Todo

from .models import ActivityLog

TIMELINE_LIMIT = 60
ATTENTION_LIMIT = 10
STALE_HOURS = 24

STATUS_LABELS = {"pending": "Not started", "in_progress": "In progress", "completed": "Completed"}
PRIORITY_LABELS = {1: "Low", 2: "Medium", 3: "High"}
FIELD_LABELS = {
    "title": "Title",
    "description": "Description",
    "status": "Status",
    "priority": "Priority",
    "due_date": "Due date",
    "category": "Category",
}


def teams_with_pm():
    """IDs of teams that have an active Project Manager."""
    return list(
        User.objects.filter(
            role=User.Role.PM, is_active=True, membership__isnull=False
        )
        .values_list("membership__team_id", flat=True)
        .distinct()
    )


def day_bounds(day):
    """[start, end) of a calendar day in the project time zone (Asia/Dhaka)."""
    start = timezone.make_aware(datetime.combine(day, time.min))
    end = timezone.make_aware(datetime.combine(day + timedelta(days=1), time.min))
    return start, end


def _short_dt(value):
    if not value:
        return "none"
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
        return timezone.localtime(parsed).strftime("%d %b %Y %H:%M")
    except (ValueError, TypeError):
        return str(value)


def _change_text(field, old, new):
    if field == "status":
        old, new = STATUS_LABELS.get(old, old), STATUS_LABELS.get(new, new)
    elif field == "priority":
        old, new = PRIORITY_LABELS.get(old, old), PRIORITY_LABELS.get(new, new)
    elif field == "due_date":
        old, new = _short_dt(old), _short_dt(new)
    elif field in ("description", "category"):
        return f"{FIELD_LABELS[field]} changed"
    return f"{FIELD_LABELS.get(field, field)}: {old} -> {new}"


def _detail(log):
    details = log.details or {}
    if log.action in (ActivityLog.Action.CREATED, ActivityLog.Action.ASSIGNED):
        return f"Assigned to {details['assignee']}" if details.get("assignee") else ""
    if log.action == ActivityLog.Action.REJECTED:
        return f"Reason: {details['reason']}" if details.get("reason") else ""
    if log.action == ActivityLog.Action.UPDATED:
        return "; ".join(
            _change_text(field, old, new)
            for field, (old, new) in (details.get("changes") or {}).items()
        )
    return ""


def _completed(log):
    if log.action != ActivityLog.Action.UPDATED:
        return False
    change = (log.details or {}).get("changes", {}).get("status")
    return bool(change) and change[1] == Todo.Status.COMPLETED


def build_team_summary(team, day, now=None):
    now = now or timezone.now()
    start, end = day_bounds(day)
    logs = list(
        ActivityLog.objects.filter(team=team, created_at__gte=start, created_at__lt=end)
        .order_by("created_at", "id")
    )
    previous_total = ActivityLog.objects.filter(
        team=team,
        created_at__gte=day_bounds(day - timedelta(days=1))[0],
        created_at__lt=start,
    ).count()

    # ---- the day's actions
    by_action = Counter(log.action for log in logs)
    completed_logs = [log for log in logs if _completed(log)]
    day_stats = {
        "total": len(logs),
        "previous_total": previous_total,
        "created": by_action[ActivityLog.Action.CREATED],
        "assigned": by_action[ActivityLog.Action.ASSIGNED],
        "accepted": by_action[ActivityLog.Action.ACCEPTED],
        "rejected": by_action[ActivityLog.Action.REJECTED],
        "updated": by_action[ActivityLog.Action.UPDATED],
        "deleted": by_action[ActivityLog.Action.DELETED],
        "completed": len(completed_logs),
    }

    # ---- where the team stands right now
    team_todos = Todo.objects.filter(team=team)
    active = team_todos.exclude(status=Todo.Status.COMPLETED).exclude(
        assignment_status=Todo.AssignmentStatus.REJECTED
    )
    overdue_q = Q(due_date__lt=now)
    stale_cutoff = now - timedelta(hours=STALE_HOURS)
    stale_q = Q(assignment_status=Todo.AssignmentStatus.PENDING, assigned_at__lt=stale_cutoff)

    overdue_qs = active.filter(overdue_q).select_related("assignee").order_by("due_date")
    stale_qs = active.filter(stale_q).select_related("assignee").order_by("assigned_at")
    snapshot = {
        "active": active.count(),
        "overdue": overdue_qs.count(),
        "awaiting": active.filter(assignment_status=Todo.AssignmentStatus.PENDING).count(),
        "stale": stale_qs.count(),
    }
    overdue_items = [
        {
            "title": t.title,
            "assignee": t.assignee.name if t.assignee else "-",
            "due": timezone.localtime(t.due_date).strftime("%d %b %Y"),
            "days": max((now - t.due_date).days, 0),
        }
        for t in overdue_qs[:ATTENTION_LIMIT]
    ]
    stale_items = [
        {
            "title": t.title,
            "assignee": t.assignee.name if t.assignee else "-",
            "since": timezone.localtime(t.assigned_at).strftime("%d %b %H:%M"),
            "hours": int((now - t.assigned_at).total_seconds() // 3600),
        }
        for t in stale_qs[:ATTENTION_LIMIT]
    ]

    # ---- per member
    per_todo = {
        row["assignee_id"]: row
        for row in active.filter(assignee__isnull=False)
        .values("assignee_id")
        .annotate(open=Count("id"), overdue=Count("id", filter=overdue_q))
    }
    actions_by_user = Counter(log.actor_id for log in logs if log.actor_id)
    completed_by_user = Counter(log.actor_id for log in completed_logs if log.actor_id)
    members = []
    for membership in Membership.objects.filter(team=team).select_related("user"):
        user = membership.user
        todo_row = per_todo.get(user.pk, {})
        members.append(
            {
                "name": user.name,
                "role": "Project Manager" if user.role == User.Role.PM else "Member",
                "actions": actions_by_user[user.pk],
                "completed": completed_by_user[user.pk],
                "open": todo_row.get("open", 0),
                "overdue": todo_row.get("overdue", 0),
            }
        )
    members.sort(key=lambda m: (-m["actions"], m["name"].lower()))

    # ---- timeline
    timeline = [
        {
            "time": timezone.localtime(log.created_at).strftime("%H:%M"),
            "actor": log.actor_name,
            "action": log.get_action_display(),
            "todo": log.todo_title,
            "detail": _detail(log),
        }
        for log in logs[:TIMELINE_LIMIT]
    ]
    rejected = [
        {"actor": log.actor_name, "todo": log.todo_title, "reason": (log.details or {}).get("reason", "")}
        for log in logs
        if log.action == ActivityLog.Action.REJECTED
    ]

    summary = {
        "team": team.name,
        "day": day,
        "generated_at": timezone.localtime(now),
        "day_stats": day_stats,
        "snapshot": snapshot,
        "overdue_items": overdue_items,
        "stale_items": stale_items,
        "rejected": rejected,
        "members": members,
        "timeline": timeline,
        "timeline_hidden": max(len(logs) - TIMELINE_LIMIT, 0),
        "stale_hours": STALE_HOURS,
    }
    summary["highlights"] = build_highlights(summary)
    return summary


def _plural(count, word):
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def build_highlights(summary):
    stats, snap = summary["day_stats"], summary["snapshot"]
    lines = []
    if stats["total"] == 0:
        lines.append("A quiet day: no todo activity was recorded for the team.")
    else:
        actors = [m for m in summary["members"] if m["actions"] > 0]
        lines.append(
            f"{_plural(stats['total'], 'action')} by {_plural(len(actors), 'team member')}."
        )
        diff = stats["total"] - stats["previous_total"]
        before = f"({stats['previous_total']} the day before)"
        if diff > 0:
            lines.append(f"Activity was up by {diff} {before}.")
        elif diff < 0:
            lines.append(f"Activity was down by {-diff} {before}.")
        else:
            lines.append(f"Activity was the same as the day before {before}.")
        if actors:
            top = actors[0]
            lines.append(f"Most active: {top['name']} ({_plural(top['actions'], 'action')}).")
        if stats["completed"]:
            lines.append(f"{_plural(stats['completed'], 'todo')} marked as completed.")
        if stats["rejected"]:
            lines.append(f"{_plural(stats['rejected'], 'assignment')} rejected. The reasons are in the report.")
    if snap["overdue"]:
        lines.append(f"{_plural(snap['overdue'], 'active todo')} overdue right now.")
    if snap["stale"]:
        lines.append(
            f"{_plural(snap['stale'], 'assignment')} waiting for an answer for more than "
            f"{summary['stale_hours']} hours."
        )
    return lines