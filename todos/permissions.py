from rest_framework.permissions import BasePermission

from .models import Todo


class CanEditTodo(BasePermission):
    """Apply the Phase 3 object rules to Todo mutations and actions."""

    message = "You do not have permission to perform this action on this todo."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user_id = request.user.pk
        action = getattr(view, "action", None)

        if action == "assign":
            return obj.assigner_id == user_id
        if action in {"accept", "reject"}:
            return obj.assignee_id == user_id
        if action == "destroy":
            return obj.assigner_id == user_id
        if action in {"partial_update", "update"}:
            if obj.assignee_id is None:
                return obj.assigner_id == user_id
            return (
                obj.assignee_id == user_id
                and obj.assignment_status != Todo.AssignmentStatus.REJECTED
            )

        # Both sides of an assignment can view the todo; the queryset already
        # prevents anybody else from discovering it.
        return obj.assigner_id == user_id or obj.assignee_id == user_id
