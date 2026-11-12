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
from drf_spectacular.utils import extend_schema_field

from core.exceptions import Conflict
from core.fields import (
    StrictCharField,
    StrictEmailField,
    StrictPrimaryKeyRelatedField,
    StrictSecretField,
)
from teams.models import Membership, Team

User = get_user_model()

EMAIL_TAKEN = "A user with this email already exists."


def user_payload(user):
    try:
        membership = user.membership
    except Membership.DoesNotExist:
        membership = None
    return {
        "id": user.pk,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "team": (
            {"id": membership.team_id, "name": membership.team.name}
            if membership is not None
            else None
        ),
    }


class AdminUserSerializer(serializers.ModelSerializer):
    role = StrictCharField(max_length=20, single_line=True, required=False)
    created_count = serializers.IntegerField(read_only=True, default=0)
    assigned_count = serializers.IntegerField(read_only=True, default=0)
    team_id = StrictPrimaryKeyRelatedField(
        source="team",
        queryset=Team.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    team = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "name",
            "email",
            "role",
            "team",
            "team_id",
            "created_count",
            "assigned_count",
        ]
        read_only_fields = [
            "id",
            "name",
            "email",
            "team",
            "created_count",
            "assigned_count",
        ]

    def validate_role(self, value):
        if value not in User.Role.values:
            raise serializers.ValidationError("Role must be either 'member' or 'admin'.")
        return value

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_team(self, obj):
        try:
            membership = obj.membership
        except Membership.DoesNotExist:
            return None
        return {"id": membership.team_id, "name": membership.team.name}

    def update(self, instance, validated_data):
        request = self.context.get("request")
        requested_role = validated_data.get("role")
        if requested_role is not None and request.user.pk == instance.pk:
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied("You cannot change your own role.")

        team_supplied = "team" in validated_data
        team = validated_data.pop("team", None)

        with transaction.atomic():
            target = User.objects.select_for_update().get(pk=instance.pk)
            if requested_role is not None and requested_role != target.role:
                if target.role == User.Role.ADMIN and requested_role != User.Role.ADMIN:
                    admin_count = User.objects.select_for_update().filter(
                        role=User.Role.ADMIN
                    ).count()
                    if admin_count <= 1:
                        raise Conflict("The last workspace admin cannot be demoted.")
                target.role = requested_role
                target.save(update_fields=["role"])

            if team_supplied:
                if team is None:
                    Membership.objects.filter(user=target).delete()
                else:
                    Membership.objects.update_or_create(
                        user=target,
                        defaults={"team": team},
                    )

        return target


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