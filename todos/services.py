from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from teams.models import Membership

from .models import Todo


def _membership(user):
    try:
        return Membership.objects.select_related("team").get(user=user)
    except Membership.DoesNotExist:
        raise PermissionDenied("You must belong to a team before assigning a todo.")


def validate_assignment(assigner, assignee):
    assigner_membership = _membership(assigner)
    try:
        assignee_membership = Membership.objects.get(user=assignee)
    except Membership.DoesNotExist:
        raise PermissionDenied("The assignee must belong to your team.")
    if assignee_membership.team_id != assigner_membership.team_id:
        raise PermissionDenied("The assignee must share a team with you.")
    return assigner_membership.team


def assign_todo(todo, assigner, assignee):
    if todo.assigner_id != assigner.pk:
        raise PermissionDenied("Only the todo assigner can assign it.")

    team = validate_assignment(assigner, assignee)
    now = timezone.now()
    assignment_status = (
        Todo.AssignmentStatus.ACCEPTED
        if assignee.pk == assigner.pk
        else Todo.AssignmentStatus.PENDING
    )
    with transaction.atomic():
        Todo.objects.filter(pk=todo.pk, assigner=assigner).update(
            assignee=assignee,
            team=team,
            assignment_status=assignment_status,
            assigned_at=now,
            responded_at=now if assignment_status == Todo.AssignmentStatus.ACCEPTED else None,
            updated_at=now,
        )

    todo.assignee = assignee
    todo.team = team
    todo.assignment_status = assignment_status
    todo.assigned_at = now
    todo.responded_at = now if assignment_status == Todo.AssignmentStatus.ACCEPTED else None
    todo.updated_at = now
    return todo
