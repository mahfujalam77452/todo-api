from rest_framework import serializers

from core.fields import StrictCharField

from .models import BulkEmail

SUBJECT_MAX = 150
MESSAGE_MAX = 5000


class BulkEmailCreateSerializer(serializers.Serializer):
    subject = StrictCharField(max_length=SUBJECT_MAX, single_line=True)
    message = StrictCharField(max_length=MESSAGE_MAX)


class BulkEmailSerializer(serializers.ModelSerializer):
    team = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = BulkEmail
        fields = [
            "id", "team", "sender_name", "subject", "message",
            "recipient_count", "sent_count", "failed_count",
            "status", "created_at", "sent_at",
        ]
        read_only_fields = fields

    def get_team(self, obj) -> dict:
        return {"id": obj.team_id, "name": obj.team.name}

    def get_status(self, obj) -> str:
        if obj.sent_at is None:
            return "sending"
        return "sent" if obj.failed_count == 0 else "partially_failed"