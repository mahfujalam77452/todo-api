import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import F, Q
from django.db.models.functions import Lower
from django.db.models.lookups import GreaterThan, LessThanOrEqual


def copy_legacy_completion_status(apps, schema_editor):
    Todo = apps.get_model("todos", "Todo")
    Todo.objects.filter(is_completed=True).update(status="completed")
    Todo.objects.filter(is_completed=False).update(status="pending")


class Migration(migrations.Migration):
    dependencies = [
        ("teams", "0001_initial"),
        ("todos", "0004_todo_user_required"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="todo", name="todo_user_created_idx"
        ),
        migrations.RemoveIndex(
            model_name="todo", name="todo_user_status_idx"
        ),
        migrations.RemoveIndex(
            model_name="todo", name="todo_user_priority_idx"
        ),
        migrations.RemoveIndex(
            model_name="todo", name="todo_user_open_due_idx"
        ),
        migrations.RemoveIndex(
            model_name="todo", name="todo_user_title_ci_idx"
        ),
        migrations.RenameField(
            model_name="todo", old_name="user", new_name="assigner"
        ),
        migrations.AlterField(
            model_name="todo",
            name="assigner",
            field=models.ForeignKey(
                db_index=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="created_todos",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="todo",
            name="assignee",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_todos",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="todo",
            name="team",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="todos",
                to="teams.team",
            ),
        ),
        migrations.AddField(
            model_name="todo",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("in_progress", "In progress"),
                    ("completed", "Completed"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="todo",
            name="assignment_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("pending", "Pending"),
                    ("accepted", "Accepted"),
                    ("rejected", "Rejected"),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="todo",
            name="assigned_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="todo",
            name="responded_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(copy_legacy_completion_status, migrations.RunPython.noop),
        migrations.RemoveField(model_name="todo", name="is_completed"),
        migrations.AddConstraint(
            model_name="todo",
            constraint=models.CheckConstraint(
                condition=Q(status__in=["pending", "in_progress", "completed"]),
                name="todo_status_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="todo",
            constraint=models.CheckConstraint(
                condition=Q(assignment_status__in=["pending", "accepted", "rejected"])
                | Q(assignment_status__isnull=True),
                name="todo_assignment_status_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="todo",
            constraint=models.CheckConstraint(
                condition=(
                    Q(assignee__isnull=True, assignment_status__isnull=True)
                    | Q(assignee__isnull=False, assignment_status__isnull=False)
                ),
                name="todo_assignment_pair_valid",
            ),
        ),
        migrations.AddIndex(
            model_name="todo",
            index=models.Index(
                fields=["assigner", "-created_at", "-id"],
                name="todo_assigner_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="todo",
            index=models.Index(
                fields=["assigner", "status", "-created_at", "-id"],
                name="todo_assigner_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="todo",
            index=models.Index(
                fields=["assigner", "priority", "-created_at", "-id"],
                name="todo_assigner_priority_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="todo",
            index=models.Index(
                condition=Q(due_date__isnull=False) & ~Q(status="completed"),
                fields=["assigner", "due_date"],
                name="todo_assigner_open_due_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="todo",
            index=models.Index(
                F("assigner"), Lower("title"), name="todo_assigner_title_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="todo",
            index=models.Index(
                fields=["assignee", "-created_at", "-id"],
                name="todo_assignee_created_idx",
            ),
        ),
    ]
