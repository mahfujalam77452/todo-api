from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q


safe_link_validator = RegexValidator(
    regex=r"^/(?!/)(?!.*://)[^\x00-\x1f]*$",
    message="Link must be a safe local path.",
)


class Notification(models.Model):
    class Type(models.TextChoices):
        ASSIGNED = "assigned", "Assigned"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        ROLE_CHANGED = "role_changed", "Role changed"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    type = models.CharField(max_length=30, choices=Type.choices)
    message = models.CharField(max_length=500)
    todo = models.ForeignKey(
        "todos.Todo",
        on_delete=models.SET_NULL,
        related_name="notifications",
        null=True,
        blank=True,
    )
    link = models.CharField(max_length=255, validators=[safe_link_validator])
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["recipient", "is_read", "-created_at", "-id"],
                name="notification_inbox_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(link__startswith="/")
                & ~Q(link__startswith="//")
                & ~Q(link__contains="://"),
                name="notification_safe_link",
            ),
            models.CheckConstraint(
                condition=Q(type__in=[
                    "assigned", "accepted", "rejected", "role_changed"
                ]),
                name="notification_type_valid",
            ),
        ]

    def __str__(self):
        return f"Notification #{self.pk} for {self.recipient_id}"
