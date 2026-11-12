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
