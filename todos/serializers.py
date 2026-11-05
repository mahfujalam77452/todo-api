from rest_framework import serializers
from django.utils import timezone
from rest_framework.exceptions import NotFound

from categories.models import Category
from core.fields import (
    StrictBooleanField,
    StrictCharField,
    StrictPrimaryKeyRelatedField,
)

from .models import Todo

DESCRIPTION_MAX_LENGTH = 10_000


class TodoSerializer(serializers.ModelSerializer):
    title = StrictCharField(max_length=255)
    description = StrictCharField(
        required=False, allow_blank=True, default="", max_length=DESCRIPTION_MAX_LENGTH
    )
    is_completed = StrictBooleanField(required=False, default=False)
    category = StrictPrimaryKeyRelatedField(
        queryset=Category.objects.all(), required=False, allow_null=True, default=None
    )
    # allow_null keeps the key present (as null) when there is no category.
    category_name = serializers.CharField(
        source="category.name", read_only=True, allow_null=True
    )

    class Meta:
        model = Todo
        fields = [
            "id",
            "title",
            "description",
            "is_completed",
            "category",
            "category_name",
            "created_at",
            "updated_at",
        ]
        # `user` is deliberately not a field: clients can never set it.
        read_only_fields = ["id", "created_at", "updated_at"]

    def update(self, instance, validated_data):
        """Write only the columns that actually changed.

        - Nothing changed (e.g. PATCH {} or the same values) -> no write and
          `updated_at` stays as it was.
        - Two clients patching *different* fields at the same time no longer
          overwrite each other: the default `instance.save()` rewrites every
          column from a possibly stale copy; this UPDATE touches only the
          changed ones.
        - `.update()` skips auto_now, so `updated_at` is set explicitly.
        """
        changed = {
            field: value
            for field, value in validated_data.items()
            if getattr(instance, field) != value
        }
        if not changed:
            return instance

        now = timezone.now()
        rows = Todo.objects.filter(pk=instance.pk).update(**changed, updated_at=now)
        if rows == 0:
            # Deleted by someone else between our read and this write.
            raise NotFound()

        for field, value in changed.items():
            setattr(instance, field, value)
        instance.updated_at = now
        return instance