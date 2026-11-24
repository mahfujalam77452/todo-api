from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    """One team action (a todo was created, accepted, ...).

    Source for the PM's action email now and the nightly PDF summary later.
    Names and the todo title are copied on purpose: the todo or user may be
    deleted later, the history must stay.
    """

    class Action(models.TextChoices):
        CREATED = "created", "Todo created"
        ASSIGNED = "assigned", "Todo assigned"
        ACCEPTED = "accepted", "Assignment accepted"
        REJECTED = "rejected", "Assignment rejected"
        UPDATED = "updated", "Todo updated"
        DELETED = "deleted", "Todo deleted"

    team = models.ForeignKey(
        "teams.Team", on_delete=models.CASCADE, related_name="activity_logs"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="activity_logs",
    )
    actor_name = models.CharField(max_length=150)
    action = models.CharField(max_length=20, choices=Action.choices)
    todo = models.ForeignKey(
        "todos.Todo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    todo_title = models.CharField(max_length=255)
    # {"assignee": "Ali", "reason": "...", "changes": {"status": ["pending", "completed"]}}
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Set after the PM email was sent, so a retry never sends it twice.
    pm_notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["team", "-created_at"], name="activity_team_created_idx"),
        ]

    def __str__(self):
        return f"{self.actor_name} {self.action}: {self.todo_title}"

class BulkEmail(models.Model):
    """An email the team's Project Manager sent to the whole team."""

    team = models.ForeignKey(
        "teams.Team", on_delete=models.CASCADE, related_name="bulk_emails"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="bulk_emails",
    )
    sender_name = models.CharField(max_length=150)
    subject = models.CharField(max_length=150)
    message = models.TextField()
    recipient_count = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    # Empty while the background task has not finished yet.
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["team", "-created_at"], name="bulkemail_team_created_idx"),
        ]

    def __str__(self):
        return f"{self.sender_name}: {self.subject}"