from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from drf_spectacular.utils import extend_schema_field

from categories.models import Category
from accounts.models import User
from core.fields import (
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
    status = StrictCharField(required=False, default="pending", single_line=True)
    is_completed = serializers.SerializerMethodField(read_only=True)
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
    assigner = serializers.SerializerMethodField()
    assignee = serializers.SerializerMethodField()
    team = serializers.SerializerMethodField()
    assignment_status = serializers.CharField(read_only=True, allow_null=True)
    assignee_id = StrictPrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = Todo
        fields = [
            "id",
            "title",
            "description",
            "status",
            "is_completed",
            "priority",
            "priority_display",
            "due_date",
            "category",
            "category_name",
            "assigner",
            "assignee",
            "assignee_id",
            "team",
            "assignment_status",
            "assigned_at",
            "responded_at",
            "created_at",
            "updated_at",
        ]
         # `user` is deliberately not a field: clients can never set it.
        read_only_fields = [
            "id",
            "is_completed",
            "assigner",
            "assignee",
            "team",
            "assignment_status",
            "assigned_at",
            "responded_at",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(serializers.BooleanField)
    def get_is_completed(self, obj) -> bool:
        return obj.status == Todo.Status.COMPLETED

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_assigner(self, obj):
        return self._user_payload(obj.assigner)

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_assignee(self, obj):
        return self._user_payload(obj.assignee)

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_team(self, obj):
        if obj.team is None:
            return None
        return {"id": obj.team.pk, "name": obj.team.name}

    @staticmethod
    def _user_payload(user):
        if user is None:
            return None
        return {"id": user.pk, "name": user.name, "email": user.email}

    def validate_status(self, value):
        if value not in Todo.Status.values:
            raise serializers.ValidationError(
                "Status must be pending, in_progress, or completed."
            )
        return value

    def validate(self, attrs):
        if self.instance is not None and "assignee_id" in attrs:
            raise serializers.ValidationError(
                {"assignee_id": "Assignment changes must use the assign action."}
            )
        return attrs
    
    def validate_due_date(self, value):
        if value is not None:
            ensure_in_year_window(value, DUE_DATE_MIN_YEAR, DUE_DATE_MAX_YEAR)
        return value

    def create(self, validated_data):
        # The view owns assigner and applies optional assignment atomically.
        validated_data.pop("assignee_id", None)
        return Todo.objects.create(**validated_data)
    


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


class AssignTodoSerializer(serializers.Serializer):
    assignee_id = StrictPrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        allow_null=False,
    )


class AssignmentResponseSerializer(serializers.Serializer):
    reason = StrictCharField(
        required=False,
        allow_blank=True,
        max_length=250,
        single_line=True,
        default="",
    )