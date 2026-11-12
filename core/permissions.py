from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """Allow only authenticated workspace administrators."""

    message = "Workspace admin access is required."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == "admin"
        )
