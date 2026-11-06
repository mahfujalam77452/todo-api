from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)

from core.fields import StrictCharField, StrictEmailField, StrictSecretField

User = get_user_model()

EMAIL_TAKEN = "A user with this email already exists."


def user_payload(user):
    return {"id": user.pk, "name": user.name, "email": user.email}


class RegisterSerializer(serializers.Serializer):
    """name, email and password in; id, name and email out (never the password).

    Only these three fields exist, so a body with is_staff, is_superuser,
    is_active, id or date_joined cannot change anything: it is simply ignored.
    """

    id = serializers.IntegerField(read_only=True)
    name = StrictCharField(max_length=150, single_line=True)
    email = StrictEmailField()
    password = StrictSecretField()

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(EMAIL_TAKEN)
        return value

    def validate(self, attrs):
        password = attrs["password"]
        if not password.strip():
            raise serializers.ValidationError({"password": ["Password cannot be only spaces."]})
        # The similarity check compares the password with the user's email and name.
        candidate = User(email=attrs["email"], name=attrs["name"])
        try:
            validate_password(password, user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs

    def create(self, validated_data):
        try:
            with transaction.atomic():
                return User.objects.create_user(
                    email=validated_data["email"],
                    password=validated_data["password"],
                    name=validated_data["name"],
                )
        except IntegrityError:
            # Two people registering the same address at the same moment.
            raise serializers.ValidationError({"email": [EMAIL_TAKEN]})

    def to_representation(self, instance):
        return user_payload(instance)


class LoginSerializer(TokenObtainPairSerializer):
    """email + password in; access, refresh and the user out.

    A wrong email, a wrong password and a deactivated account all give the same
    401, so the answer does not reveal which addresses are registered.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"] = StrictEmailField(check_format=False, write_only=True)
        self.fields["password"] = StrictSecretField()

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = user_payload(self.user)
        return data


class RefreshSerializer(TokenRefreshSerializer):
    """simplejwt looks the user up with .get(): for a deleted user that raised
    DoesNotExist, which became a 500. A deleted user is simply not logged in."""

    def validate(self, attrs):
        try:
            return super().validate(attrs)
        except User.DoesNotExist:
            raise AuthenticationFailed(
                self.error_messages["no_active_account"], "no_active_account"
            )


class LogoutSerializer(serializers.Serializer):
    refresh = StrictSecretField(max_length=4096)