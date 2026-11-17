from django.db.models.functions import Lower
from rest_framework import serializers

from core.fields import StrictCharField

from .models import Team


class TeamSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["id", "name"]
        read_only_fields = fields


class TeamSerializer(serializers.ModelSerializer):
    name = StrictCharField(max_length=100, single_line=True)

    class Meta:
        model = Team
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_name(self, value):
        queryset = Team.objects.annotate(name_lower=Lower("name")).filter(
            name_lower=value.lower()
        )
        instance = self.instance
        if instance is not None:
            queryset = queryset.exclude(pk=instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A team with this name already exists.")
        return value
