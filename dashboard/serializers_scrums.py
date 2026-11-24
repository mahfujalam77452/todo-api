from rest_framework import serializers

from scrums.models import Scrum


class ScrumSerializer(serializers.ModelSerializer):
    team_name = serializers.CharField(source="team.name", read_only=True)

    class Meta:
        model = Scrum
        fields = ["id", "team", "team_name", "name", "status", "started_at", "ended_at", "created_at"]
        read_only_fields = ["name", "status", "started_at", "ended_at", "created_at"]
