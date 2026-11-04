from django.db import IntegrityError, transaction
from django.db.models import Value
from django.db.models.functions import Lower
from rest_framework import serializers

from core.fields import StrictCharField

from .models import Category, normalize_name

DUPLICATE_MESSAGE = "A category with this name already exists."


class CategorySerializer(serializers.ModelSerializer):
    name = StrictCharField(max_length=50)

    class Meta:
        model = Category
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_name(self, value):
        value = normalize_name(value)
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        # Compare with the same Lower() the DB constraint uses, so this check
        # and the constraint can never disagree. Exclude self so that
        # PATCH {"name": "work"} on "Work" (a case-only rename) is allowed.
        duplicates = Category.objects.annotate(_lower=Lower("name")).filter(
            _lower=Lower(Value(value))
        )
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(DUPLICATE_MESSAGE)
        return value

    def save(self, **kwargs):
        # Two requests can pass validate_name at the same moment; the DB
        # constraint then rejects the second one. Report it as a 400, not a 500.
        try:
            with transaction.atomic():
                return super().save(**kwargs)
        except IntegrityError:
            raise serializers.ValidationError({"name": [DUPLICATE_MESSAGE]})