from rest_framework import status
from django.db.models import Count
from rest_framework import permissions
from rest_framework.generics import CreateAPIView, GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.throttling import ScopedRateThrottle
from drf_spectacular.utils import OpenApiResponse, extend_schema

from core.permissions import IsAdminRole
from core.schema import ErrorResponseSerializer, ValidationErrorResponseSerializer
from .models import User
from .serializers import (
    AdminUserSerializer,
    LoginSerializer,
    LogoutSerializer,
    RefreshSerializer,
    RegisterSerializer,
    user_payload,
)

# The four endpoints below are public. Each one also sets authentication_classes
# to [] on purpose: with the default JWT authentication a request carrying an
# old or broken Authorization header would be refused with 401 before the view
# even looked at it (a user with an expired token could not log in again).


class RegisterView(CreateAPIView):
    serializer_class = RegisterSerializer
    authentication_classes = []
    permission_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"

    @extend_schema(
        tags=["Authentication"],
        responses={
            201: RegisterSerializer,
            400: OpenApiResponse(ValidationErrorResponseSerializer),
            429: OpenApiResponse(ErrorResponseSerializer),
        },
        auth=[],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Authentication"],
        responses={200: OpenApiResponse(description="Current authenticated user.")},
    )
    def get(self, request):
        user = User.objects.select_related("membership__team").get(pk=request.user.pk)
        return Response(user_payload(user))


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    authentication_classes = []
    permission_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(
        tags=["Authentication"],
        responses={
            200: LoginSerializer,
            401: OpenApiResponse(ErrorResponseSerializer),
            429: OpenApiResponse(ErrorResponseSerializer),
        },
        auth=[],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class RefreshView(TokenRefreshView):
    """Exchange a refresh token for a new access token and a new refresh token
    (the old refresh token stops working)."""

    serializer_class = RefreshSerializer
    authentication_classes = []
    permission_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token"

    @extend_schema(
        tags=["Authentication"],
        responses={
            200: RefreshSerializer,
            401: OpenApiResponse(ErrorResponseSerializer),
            429: OpenApiResponse(ErrorResponseSerializer),
        },
        auth=[],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class LogoutView(GenericAPIView):
    """Blacklist a refresh token.

    Holding the refresh token is the proof, so no access token is needed: a
    user whose access token already expired can still log out. Access tokens
    already issued stay valid until they expire (15 minutes); that is how
    JWTs work.
    """

    serializer_class = LogoutSerializer
    authentication_classes = []
    permission_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token"

    @extend_schema(
        tags=["Authentication"],
        responses={
            204: None,
            400: OpenApiResponse(ValidationErrorResponseSerializer),
            401: OpenApiResponse(ErrorResponseSerializer),
            429: OpenApiResponse(ErrorResponseSerializer),
        },
        auth=[],
    )

    def get_authenticate_header(self, request):
        # With no authentication classes DRF has no WWW-Authenticate header to
        # offer, and then rewrites every 401 into a 403. A bad refresh token
        # is a 401 (simplejwt's own views do the same).
        return 'Bearer realm="api"'

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError as exc:
            raise InvalidToken(exc.args[0])
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminUserViewSet(ModelViewSet):
    queryset = User.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminRole]
    http_method_names = ["get", "patch", "head", "options"]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["role", "membership__team"]
    search_fields = ["email", "name"]

    def get_queryset(self):
        return (
            User.objects.select_related("membership__team")
            .annotate(
                created_count=Count("created_todos", distinct=True),
                assigned_count=Count("assigned_todos", distinct=True),
            )
            .order_by("email")
        )