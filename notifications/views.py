from django.utils import timezone
from rest_framework import mixins, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.viewsets import GenericViewSet
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view

from core.schema import ErrorResponseSerializer

from .models import Notification
from .serializers import (
    NotificationSerializer,
    ReadAllResponseSerializer,
    UnreadCountSerializer,
)


@extend_schema_view(
    list=extend_schema(
        tags=["Notifications"],
        responses={200: NotificationSerializer},
        description="List notifications belonging to the authenticated user.",
    ),
)
class NotificationViewSet(mixins.ListModelMixin, GenericViewSet):
    queryset = Notification.objects.none()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "notifications"
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        queryset = Notification.objects.filter(recipient=self.request.user)
        is_read = self.request.query_params.get("is_read")
        if is_read is not None:
            if is_read.lower() not in {"true", "false"}:
                from rest_framework.exceptions import ValidationError

                raise ValidationError({"is_read": ["Use true or false."]})
            queryset = queryset.filter(is_read=is_read.lower() == "true")
        return queryset

    @extend_schema(
        responses={200: UnreadCountSerializer},
        description="Return the authenticated user's unread notification count.",
    )
    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        return Response({"count": self.get_queryset().filter(is_read=False).count()})

    @extend_schema(
        responses={
            200: NotificationSerializer,
            404: OpenApiResponse(ErrorResponseSerializer),
        },
        description="Mark one of the authenticated user's notifications as read.",
    )
    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at"])
        return Response(self.get_serializer(notification).data)

    @extend_schema(
        responses={200: ReadAllResponseSerializer},
        description="Mark all of the authenticated user's notifications as read.",
    )
    @action(detail=False, methods=["post"], url_path="read-all")
    def mark_all_read(self, request):
        now = timezone.now()
        updated = self.get_queryset().filter(is_read=False).update(
            is_read=True, read_at=now
        )
        return Response({"updated": updated}, status=status.HTTP_200_OK)
