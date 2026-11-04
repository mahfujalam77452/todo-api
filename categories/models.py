import unicodedata

from django.db import models
from django.db.models import Q
from django.db.models.functions import Length, Lower
from django.db.models.lookups import GreaterThan, LessThanOrEqual


def normalize_name(value: str) -> str:
    """Trim and Unicode-normalise (NFC) so visually identical names are equal."""
    return unicodedata.normalize("NFC", (value or "").strip())


class Category(models.Model):
    """A global label, managed by admins and chosen by users on their todos."""

    name = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"
        constraints = [
            # "Work" and "work" are the same category.
            models.UniqueConstraint(Lower("name"), name="category_name_ci_unique"),
            # SQLite does not enforce VARCHAR(50); enforce 1..50 ourselves.
            models.CheckConstraint(
                condition=Q(GreaterThan(Length("name"), 0))
                & Q(LessThanOrEqual(Length("name"), 50)),
                name="category_name_length_1_50",
            ),
        ]

    def clean(self):
        super().clean()
        self.name = normalize_name(self.name)  # runs before unique checks (admin)

    def save(self, *args, **kwargs):
        self.name = normalize_name(self.name)  # safety net for any code path
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name