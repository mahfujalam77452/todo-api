from rest_framework import status
from rest_framework.generics import CreateAPIView, GenericAPIView
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.throttling import ScopedRateThrottle
from .serializers import (
    LoginSerializer,
    LogoutSerializer,
    RefreshSerializer,
    RegisterSerializer,
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


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    authentication_classes = []
    permission_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class RefreshView(TokenRefreshView):
    """Exchange a refresh token for a new access token and a new refresh token
    (the old refresh token stops working)."""

    serializer_class = RefreshSerializer
    authentication_classes = []
    permission_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token"


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