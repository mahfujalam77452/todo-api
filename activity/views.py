from django.db import transaction
from rest_framework import mixins, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.viewsets import GenericViewSet
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view

from core.exceptions import Conflict
from core.permissions import IsPMRole
from core.schema import ErrorResponseSerializer, ValidationErrorResponseSerializer
from teams.models import Membership

from .models import BulkEmail
from .serializers import BulkEmailCreateSerializer, BulkEmailSerializer
from .tasks import send_bulk_email


def _pm_team(user):
    membership = Membership.objects.select_related("team").filter(user=user).first()
    if membership is None:
        raise PermissionDenied("You are not a member of any team.")
    return membership.team


@extend_schema_view(
    list=extend_schema(
        tags=["Project Manager"],
        responses={200: BulkEmailSerializer, 403: OpenApiResponse(ErrorResponseSerializer)},
        description="Bulk emails sent by the Project Manager to their team (newest first).",
    ),
    create=extend_schema(
        tags=["Project Manager"],
        request=BulkEmailCreateSerializer,
        responses={
            202: BulkEmailSerializer,
            400: OpenApiResponse(ValidationErrorResponseSerializer),
            403: OpenApiResponse(ErrorResponseSerializer),
            409: OpenApiResponse(ErrorResponseSerializer),
            429: OpenApiResponse(ErrorResponseSerializer),
        },
        description=(
            "Send an email to every other member of the Project Manager's own team. "
            "It is sent in the background, so the answer is 202 Accepted."
        ),
    ),
)
class BulkEmailViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, GenericViewSet):
    queryset = BulkEmail.objects.none()
    serializer_class = BulkEmailSerializer
    permission_classes = [IsPMRole]
    http_method_names = ["get", "post", "head", "options"]
    # A PM cannot mail another team: the team always comes from the PM's own membership.

    def get_throttles(self):
        throttles = super().get_throttles()
        if getattr(self, "action", None) == "create":
            self.throttle_scope = "bulk_email"
            throttles.append(ScopedRateThrottle())
        return throttles

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return BulkEmail.objects.none()
        return BulkEmail.objects.filter(sender=self.request.user).select_related("team")

    def create(self, request, *args, **kwargs):
        input_serializer = BulkEmailCreateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        team = _pm_team(request.user)

        recipient_ids = list(
            Membership.objects.filter(team=team, user__is_active=True)
            .exclude(user=request.user)
            .values_list("user_id", flat=True)
        )
        if not recipient_ids:
            raise Conflict("Your team has no other members to email.")

        with transaction.atomic():
            bulk = BulkEmail.objects.create(
                team=team,
                sender=request.user,
                sender_name=request.user.name,
                recipient_count=len(recipient_ids),
                **input_serializer.validated_data,
            )
            # robust=True: a broker (Redis) problem is logged, the record stays
            # with status "sending" instead of the request failing with a 500.
            transaction.on_commit(
                lambda: send_bulk_email.delay(bulk.pk, recipient_ids), robust=True
            )

        return Response(BulkEmailSerializer(bulk).data, status=status.HTTP_202_ACCEPTED)