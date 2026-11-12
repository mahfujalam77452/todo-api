from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm as BaseUserChangeForm

from .models import User


class UserCreationForm(AdminUserCreationForm):
    """Admin 'add user' form: email + name + password (no username)."""

    class Meta:
        model = User
        fields = ("email", "name", "role")
        field_classes = {}


class UserChangeForm(BaseUserChangeForm):
    class Meta:
        model = User
        fields = "__all__"
        field_classes = {}