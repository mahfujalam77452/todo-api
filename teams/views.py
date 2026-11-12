from rest_framework import permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view

from core.schema import ErrorResponseSerializer

from .models import Membership, Team
from .serializers import TeamSerializer


@extend_schema_view(
    list=extend_schema(
        tags=["Teams"],
        responses={200: TeamSerializer},
        description="List all workspace teams.",
    ),
    retrieve=extend_schema(
        tags=["Teams"],
        responses={200: TeamSerializer, 404: OpenApiResponse(ErrorResponseSerializer)},
    ),
)
class TeamViewSet(ReadOnlyModelViewSet):
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None
    lookup_value_regex = r"[1-9][0-9]{0,17}"

    @extend_schema(
        responses={200: TeamSerializer, 403: OpenApiResponse(ErrorResponseSerializer)},
        description="List members of the authenticated user's team.",
    )
    @action(detail=True, methods=["get"], url_path="members")
    def members(self, request, pk=None):
        team = self.get_object()
        try:
            membership = request.user.membership
        except Membership.DoesNotExist:
            membership = None
        if membership is None or membership.team_id != team.pk:
            raise PermissionDenied("You can only view members of your own team.")

        members = team.memberships.select_related("user").order_by("user__name", "user_id")
        data = [
            {"id": member.user_id, "name": member.user.name, "email": member.user.email}
            for member in members
        ]
        return Response(data, status=status.HTTP_200_OK)
