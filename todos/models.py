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

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    is_completed = models.BooleanField(default=False)
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
    # null=True only until Phase 4 (auth). It becomes non-null in Task 4.4.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="todos",
        # The composite indexes below all start with user, so a separate
        # user_id index would be redundant (it would only slow writes down).
        db_index=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        # Every query of the API is scoped to one user , so every
        # index starts with `user`. Each one serves a real query shape:
        indexes = [
            # default list: newest first, and the user's total count
            models.Index(fields=["user", "-created_at", "-id"], name="todo_user_created_idx"),
            # ?status=completed|pending
            models.Index(
                fields=["user", "is_completed", "-created_at", "-id"], name="todo_user_status_idx"
            ),
            # ?priority=3
            models.Index(
                fields=["user", "priority", "-created_at", "-id"], name="todo_user_priority_idx"
            ),
            # ?overdue=true: only open todos with a due date, so the index stays small
            models.Index(
                fields=["user", "due_date"],
                condition=Q(is_completed=False, due_date__isnull=False),
                name="todo_user_open_due_idx",
            ),
            # ?ordering=title (case-insensitive)
            models.Index(F("user"), Lower("title"), name="todo_user_title_ci_idx"),
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
        ]
    def __str__(self):
        
        return f"Todo #{self.pk}"
    