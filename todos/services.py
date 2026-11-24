from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from teams.models import Membership
from activity.models import ActivityLog
from activity.services import record_activity
from notifications.services import notify_accepted, notify_assigned, notify_rejected
from scrums.models import Scrum

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


def assign_todo(todo, assigner, assignee,record = True):
    if todo.assigner_id != assigner.pk:
        raise PermissionDenied("Only the todo assigner can assign it.")

    team = validate_assignment(assigner, assignee)
    active_scrum = Scrum.objects.filter(
        team=team, status=Scrum.Status.RUNNING
    ).order_by("-started_at", "-id").first()
    now = timezone.now()
    assignment_status = (
        Todo.AssignmentStatus.ACCEPTED
        if assignee.pk == assigner.pk
        else Todo.AssignmentStatus.PENDING
    )
    assignment_update = {
        "assignee": assignee,
        "team": team,
        "assignment_status": assignment_status,
        "assigned_at": now,
        "responded_at": now if assignment_status == Todo.AssignmentStatus.ACCEPTED else None,
        "updated_at": now,
    }
    if active_scrum is not None:
        assignment_update["scrum"] = active_scrum
    with transaction.atomic():
        Todo.objects.filter(pk=todo.pk, assigner=assigner).update(
            **assignment_update,
        )
        if assignee.pk != assigner.pk:
            notify_assigned(todo, assignee)
                
        if record:
            record_activity(
                assigner, ActivityLog.Action.ASSIGNED, todo, {"assignee": assignee.name}
            )

    todo.assignee = assignee
    todo.team = team
    if active_scrum is not None:
        todo.scrum = active_scrum
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
            locked = Todo.objects.select_for_update(of=("self",)).select_related(
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
        record_activity(
            assignee,
            ActivityLog.Action.ACCEPTED if accepted else ActivityLog.Action.REJECTED,
            locked,
            {"reason": reason} if reason else {},
        )
        todo = locked
    return todo
