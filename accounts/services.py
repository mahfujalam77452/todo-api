"""One Project Manager per team, and a PM must belong to a team."""
from core.exceptions import Conflict
from teams.models import Team

from .models import User


def get_team_pm(team, exclude_user_id=None):
    queryset = User.objects.filter(role=User.Role.PM, membership__team=team)
    if exclude_user_id is not None:
        queryset = queryset.exclude(pk=exclude_user_id)
    return queryset.first()


def ensure_team_has_no_other_pm(team, user):
    """Call inside transaction.atomic(). Locks the team row so two admins can't race."""
    Team.objects.select_for_update().get(pk=team.pk)
    existing = get_team_pm(team, exclude_user_id=user.pk)
    if existing is not None:
        raise Conflict(
            f"Team '{team.name}' already has a Project Manager ({existing.name}). "
            "Change their role first."
        )