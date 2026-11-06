from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import NotFound

from categories.models import Category
from core.fields import (
    StrictBooleanField,
    StrictCharField,
    StrictDateTimeField,
    StrictIntegerChoiceField,
    StrictPrimaryKeyRelatedField,
    ensure_in_year_window,
)

from .models import Todo

DESCRIPTION_MAX_LENGTH = 10_000
# Sanity window for due dates. It also keeps absurd values (year 1 or 9999)
# away from the database, where time-zone conversion would overflow.
DUE_DATE_MIN_YEAR = 2000
DUE_DATE_MAX_YEAR = 2099


class TodoSerializer(serializers.ModelSerializer):
    title = StrictCharField(max_length=255, single_line=True)
    description = StrictCharField(
        required=False, allow_blank=True, default="", max_length=DESCRIPTION_MAX_LENGTH
    )
    is_completed = StrictBooleanField(required=False, default=False)
    priority = StrictIntegerChoiceField(
        choices=Todo.Priority.choices,
        required=False,
        default=Todo.Priority.MEDIUM,
    )
    priority_display = serializers.CharField(
        source="get_priority_display", read_only=True
    )
    # Past dates are allowed on purpose (logging old work, catching overdue).
    due_date = StrictDateTimeField(required=False, allow_null=True, default=None)
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
            "priority",
            "priority_display",
            "due_date",
            "category",
            "category_name",
            "created_at",
            "updated_at",
        ]
         # `user` is deliberately not a field: clients can never set it.
        read_only_fields = ["id", "created_at", "updated_at"]
    
    def validate_due_date(self, value):
        if value is not None:
            ensure_in_year_window(value, DUE_DATE_MIN_YEAR, DUE_DATE_MAX_YEAR)
        return value
    


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