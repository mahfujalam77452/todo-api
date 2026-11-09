from rest_framework import serializers


class ErrorResponseSerializer(serializers.Serializer):
    error = serializers.CharField()
    code = serializers.IntegerField()


class ValidationErrorResponseSerializer(ErrorResponseSerializer):
    details = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField())
    )


class HealthResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
