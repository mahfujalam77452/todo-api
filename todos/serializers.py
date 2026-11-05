from rest_framework import serializers

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