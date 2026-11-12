import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q
from notifications.models import safe_link_validator


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("todos", "0005_assignment_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("assigned", "Assigned"),
                            ("accepted", "Accepted"),
                            ("rejected", "Rejected"),
                            ("role_changed", "Role changed"),
                        ],
                        max_length=30,
                    ),
                ),
                ("message", models.CharField(max_length=500)),
                (
                    "link",
                    models.CharField(
                        max_length=255,
                        validators=[safe_link_validator],
                    ),
                ),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                (
                    "recipient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "todo",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="notifications",
                        to="todos.todo",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(
                        fields=["recipient", "is_read", "-created_at", "-id"],
                        name="notification_inbox_idx",
                    )
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=Q(link__startswith="/")
                        & ~Q(link__startswith="//")
                        & ~Q(link__contains="://"),
                        name="notification_safe_link",
                    ),
                    models.CheckConstraint(
                        condition=Q(
                            type__in=[
                                "assigned",
                                "accepted",
                                "rejected",
                                "role_changed",
                            ]
                        ),
                        name="notification_type_valid",
                    ),
                ],
            },
        ),
    ]
