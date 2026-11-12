from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Length, Lower
from django.db.models.lookups import GreaterThan, LessThanOrEqual

class Todo(models.Model):
    class Priority(models.IntegerChoices):
        LOW = 1, "Low"
        MEDIUM = 2, "Medium"
        HIGH = 3, "High"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"

    class AssignmentStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    due_date = models.DateTimeField(null=True, blank=True)
    priority = models.PositiveSmallIntegerField(
        choices=Priority.choices, default=Priority.MEDIUM
    )
    # Many todos -> one category. Deleting a category keeps its todos and
    # simply clears their category (SET_NULL).
    category = models.ForeignKey(
        "categories.Category",
        on_delete=models.SET_NULL,
        related_name="todos",
        null=True,
        blank=True,
    )
    assigner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_todos",
        db_index=False,
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_todos",
        null=True,
        blank=True,
    )
    team = models.ForeignKey(
        "teams.Team",
        on_delete=models.SET_NULL,
        related_name="todos",
        null=True,
        blank=True,
    )
    assignment_status = models.CharField(
        max_length=20,
        choices=AssignmentStatus.choices,
        null=True,
        blank=True,
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        # List queries are scoped to either the assigner or assignee.
        indexes = [
            models.Index(
                fields=["assigner", "-created_at", "-id"],
                name="todo_assigner_created_idx",
            ),
            models.Index(
                fields=["assigner", "status", "-created_at", "-id"],
                name="todo_assigner_status_idx",
            ),
            models.Index(
                fields=["assigner", "priority", "-created_at", "-id"],
                name="todo_assigner_priority_idx",
            ),
            models.Index(
                fields=["assigner", "due_date"],
                condition=Q(due_date__isnull=False) & ~Q(status="completed"),
                name="todo_assigner_open_due_idx",
            ),
            models.Index(
                F("assigner"), Lower("title"), name="todo_assigner_title_idx"
            ),
            models.Index(
                fields=["assignee", "-created_at", "-id"],
                name="todo_assignee_created_idx",
            ),
        ]
        constraints = [
            # SQLite does NOT enforce VARCHAR(255); enforce it ourselves.
            models.CheckConstraint(
                condition=Q(GreaterThan(Length("title"), 0))
                & Q(LessThanOrEqual(Length("title"), 255)),
                name="todo_title_length_1_255",
            ),
            models.CheckConstraint(
                condition=Q(priority__in=[1, 2, 3]),
                name="todo_priority_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["pending", "in_progress", "completed"]),
                name="todo_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(assignment_status__in=["pending", "accepted", "rejected"])
                | Q(assignment_status__isnull=True),
                name="todo_assignment_status_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(assignee__isnull=True, assignment_status__isnull=True)
                    | Q(assignee__isnull=False, assignment_status__isnull=False)
                ),
                name="todo_assignment_pair_valid",
            ),
        ]
    def __str__(self):
        
        return f"Todo #{self.pk}"
    