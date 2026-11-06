from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.settings import api_settings


def _is_user_id(claim) -> bool:
    """A real whole number (or the digits of one) that fits a 64-bit column."""
    if type(claim) is int:  # not bool, which is a subclass of int
        return 0 < claim < 2**63
    return isinstance(claim, str) and claim.isascii() and claim.isdigit() and 0 < int(claim) < 2**63


class SafeJWTAuthentication(JWTAuthentication):
    """JWT authentication that never turns a strange token into a 500 or a
    wrong user.

    simplejwt looks the user up with User.objects.get(id=<user_id claim>). With
    a validly signed token whose claim is "abc", [1] or 2**70 that call raised
    ValueError/TypeError/OverflowError (a 500), and with 1.5 or true Django
    quietly turned it into user 1. Our server never issues such tokens, so only
    a leaked signing key could produce one, but a bad token must be a plain 401.
    """

    def get_user(self, validated_token):
        claim = validated_token.get(api_settings.USER_ID_CLAIM)
        if claim is not None and not _is_user_id(claim):
            raise AuthenticationFailed("User not found", code="user_not_found")
        try:
            return super().get_user(validated_token)
        except (ValueError, TypeError, OverflowError):
            raise AuthenticationFailed("User not found", code="user_not_found")