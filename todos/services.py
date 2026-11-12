from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from teams.models import Membership
from notifications.services import notify_accepted, notify_assigned, notify_rejected

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
        if assignee.pk != assigner.pk:
            notify_assigned(todo, assignee)

    todo.assignee = assignee
    todo.team = team
    todo.assignment_status = assignment_status
    todo.assigned_at = now
    todo.responded_at = now if assignment_status == Todo.AssignmentStatus.ACCEPTED else None
    todo.updated_at = now
    return todo


def respond_to_assignment(todo, assignee, accepted, reason=None):
    if todo.assignee_id != assignee.pk:
        raise PermissionDenied("Only the assignee can respond to this assignment.")

    new_status = (
        Todo.AssignmentStatus.ACCEPTED
        if accepted
        else Todo.AssignmentStatus.REJECTED
    )
    now = timezone.now()
    with transaction.atomic():
        try:
            locked = Todo.objects.select_for_update().select_related(
                "assigner", "assignee"
            ).get(pk=todo.pk)
        except Todo.DoesNotExist:
            from rest_framework.exceptions import NotFound

            raise NotFound()
        rows = Todo.objects.filter(
            pk=locked.pk,
            assignee=assignee,
            assignment_status=Todo.AssignmentStatus.PENDING,
        ).update(assignment_status=new_status, responded_at=now, updated_at=now)
        if rows == 0:
            from core.exceptions import Conflict

            raise Conflict("This assignment is no longer pending.")

        locked.assignment_status = new_status
        locked.responded_at = now
        locked.updated_at = now
        if accepted:
            notify_accepted(locked, locked.assigner)
        else:
            notify_rejected(locked, locked.assigner, reason=reason)
        todo = locked
    return todo
