from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    todo_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "type",
            "message",
            "todo_id",
            "link",
            "is_read",
            "created_at",
            "read_at",
        ]
        read_only_fields = fields


class UnreadCountSerializer(serializers.Serializer):
    count = serializers.IntegerField()


class ReadAllResponseSerializer(serializers.Serializer):
    updated = serializers.IntegerField()
