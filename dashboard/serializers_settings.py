from rest_framework import serializers

from .models import DashboardSetting


class DashboardSettingSerializer(serializers.ModelSerializer):
    class Meta:
        model = DashboardSetting
        fields = ["overloaded_user_threshold", "overdue_alert_threshold"]

    def validate_overloaded_user_threshold(self, value):
        if value < 1:
            raise serializers.ValidationError("The overloaded-user threshold must be at least 1.")
        return value
