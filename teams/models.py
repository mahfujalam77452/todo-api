import unicodedata

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class Team(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="team_name_ci_unique"),
        ]

    def clean(self):
        super().clean()
        self.name = unicodedata.normalize("NFC", (self.name or "").strip())

    def save(self, *args, **kwargs):
        self.name = unicodedata.normalize("NFC", (self.name or "").strip())
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Membership(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="membership",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["team_id", "user_id"]

    def clean(self):
        super().clean()
        from accounts.models import User

        if getattr(self.user, "role", None) == User.Role.PM and self.team_id:
            other = (
                User.objects.filter(role=User.Role.PM, membership__team_id=self.team_id)
                .exclude(pk=self.user_id)
                .first()
            )
            if other is not None:
                from django.core.exceptions import ValidationError

                raise ValidationError(f"This team already has a Project Manager ({other.name}).")

    def __str__(self):
        return f"{self.user} – {self.team}"
