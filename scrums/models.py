from django.db import models


class Scrum(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        RUNNING = "running", "Running"
        ENDED = "ended", "End"

    team = models.ForeignKey("teams.Team", on_delete=models.CASCADE, related_name="scrums")
    name = models.CharField(max_length=150)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-started_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["team"],
                condition=models.Q(status="running"),
                name="one_active_scrum_per_team",
            ),
        ]
        indexes = [models.Index(fields=["team", "status", "-started_at"])]

    def __str__(self):
        return f"{self.team.name}: {self.name}"
