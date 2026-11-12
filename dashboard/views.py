from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiResponse, extend_schema

from core.permissions import IsAdminRole
from core.schema import ErrorResponseSerializer
from todos.models import Todo
from todos.serializers import TodoSerializer
from teams.models import Membership, Team

from .serializers import (
    ActivitySerializer,
    DashboardTeamSerializer,
    DashboardUserSerializer,
    OverviewSerializer,
)

User = get_user_model()


class AdminReadOnlyAPIView(APIView):
    permission_classes = [IsAdminRole]
    http_method_names = ["get", "head", "options"]


def _percentage(numerator, denominator):
    if not denominator:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def _team_payload(user):
    try:
        membership = user.membership
    except Membership.DoesNotExist:
        return None
    return {"id": membership.team_id, "name": membership.team.name}


def _user_rows():
    return User.objects.select_related("membership__team").annotate(
        created_count=Count("created_todos", distinct=True),
        assigned_count=Count("assigned_todos", distinct=True),
        completed_count=Count(
            "assigned_todos",
            filter=Q(assigned_todos__status=Todo.Status.COMPLETED),
            distinct=True,
        ),
        rejected_count=Count(
            "assigned_todos",
            filter=Q(
                assigned_todos__assignment_status=Todo.AssignmentStatus.REJECTED
            ),
            distinct=True,
        ),
    )


def _user_payload(user):
    return {
        "id": user.pk,
        "name": user.name,
        "email": user.email,
        "role": user.role,
        "team": _team_payload(user),
        "created_count": user.created_count,
        "assigned_count": user.assigned_count,
        "completed_count": user.completed_count,
        "rejected_count": user.rejected_count,
        "completion_rate": _percentage(user.completed_count, user.assigned_count),
        "rejection_rate": _percentage(user.rejected_count, user.assigned_count),
    }


class OverviewView(AdminReadOnlyAPIView):
    @extend_schema(
        tags=["Admin Dashboard"],
        responses={200: OverviewSerializer},
        description="Database-backed workspace overview metrics for administrators.",
    )
    def get(self, request):
        now = timezone.now()
        total_todos = Todo.objects.count()
        completed_todos = Todo.objects.filter(status=Todo.Status.COMPLETED).count()
        pending_assignments = Todo.objects.filter(
            assignment_status=Todo.AssignmentStatus.PENDING
        ).count()
        pending_seven_days = Todo.objects.filter(
            assignment_status=Todo.AssignmentStatus.PENDING,
            assigned_at__isnull=False,
            assigned_at__lte=now - timedelta(days=7),
        ).count()
        overdue = Todo.objects.filter(
            due_date__isnull=False,
            due_date__lt=now,
        ).exclude(status=Todo.Status.COMPLETED).count()

        rejected_users = [
            {
                "id": user.pk,
                "name": user.name,
                "rejection_rate": _percentage(
                    user.rejected_count, user.assigned_count
                ),
            }
            for user in _user_rows().order_by("-rejected_count", "email")
            if user.rejected_count and _percentage(
                user.rejected_count, user.assigned_count
            ) >= 50
        ][:10]

        return Response(
            {
                "users": User.objects.count(),
                "teams": Team.objects.count(),
                "todos": total_todos,
                "incomplete_todos": total_todos - completed_todos,
                "completed_todos": completed_todos,
                "pending_assignments": pending_assignments,
                "completion_rate": _percentage(completed_todos, total_todos),
                "bottlenecks": {
                    "pending_assignments_over_7_days": pending_seven_days,
                    "overdue_todos": overdue,
                    "high_rejection_users": rejected_users,
                },
            }
        )


class DashboardUsersView(AdminReadOnlyAPIView):
    @extend_schema(
        tags=["Admin Dashboard"],
        responses={200: DashboardUserSerializer(many=True)},
    )
    def get(self, request):
        queryset = _user_rows().order_by("email")
        search = request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(Q(email__icontains=search) | Q(name__icontains=search))
        return Response([_user_payload(user) for user in queryset])


class DashboardTeamsView(AdminReadOnlyAPIView):
    @extend_schema(
        tags=["Admin Dashboard"],
        responses={200: DashboardTeamSerializer(many=True)},
    )
    def get(self, request):
        teams = Team.objects.annotate(
            member_count=Count("memberships", distinct=True),
            todo_count=Count("todos", distinct=True),
            completed_count=Count(
                "todos",
                filter=Q(todos__status=Todo.Status.COMPLETED),
                distinct=True,
            ),
            pending_assignment_count=Count(
                "todos",
                filter=Q(
                    todos__assignment_status=Todo.AssignmentStatus.PENDING
                ),
                distinct=True,
            ),
        ).order_by("name", "id")
        data = [
            {
                "id": team.pk,
                "name": team.name,
                "member_count": team.member_count,
                "todo_count": team.todo_count,
                "completed_count": team.completed_count,
                "pending_assignment_count": team.pending_assignment_count,
                "completion_rate": _percentage(
                    team.completed_count, team.todo_count
                ),
            }
            for team in teams
        ]
        return Response(data)


class DashboardActivityView(AdminReadOnlyAPIView):
    @extend_schema(
        tags=["Admin Dashboard"],
        responses={200: ActivitySerializer(many=True)},
    )
    def get(self, request):
        try:
            limit = int(request.query_params.get("limit", "50"))
        except ValueError:
            return Response({"error": "limit must be an integer.", "code": 400}, status=400)
        if not 1 <= limit <= 100:
            return Response(
                {"error": "limit must be between 1 and 100.", "code": 400},
                status=400,
            )

        todos = Todo.objects.select_related("assigner", "assignee").order_by(
            "-updated_at", "-id"
        )[:limit]
        events = []
        for todo in todos:
            if todo.assigned_at is not None:
                events.append(
                    {
                        "type": "assigned",
                        "todo_id": todo.pk,
                        "title": todo.title,
                        "user_id": todo.assignee_id,
                        "occurred_at": todo.assigned_at,
                        "assignment_status": todo.assignment_status,
                    }
                )
            if todo.responded_at is not None:
                events.append(
                    {
                        "type": todo.assignment_status or "responded",
                        "todo_id": todo.pk,
                        "title": todo.title,
                        "user_id": todo.assignee_id,
                        "occurred_at": todo.responded_at,
                        "assignment_status": todo.assignment_status,
                    }
                )
            events.append(
                {
                    "type": "updated",
                    "todo_id": todo.pk,
                    "title": todo.title,
                    "user_id": todo.assigner_id,
                    "occurred_at": todo.updated_at,
                    "assignment_status": todo.assignment_status,
                }
            )
        events.sort(key=lambda event: event["occurred_at"], reverse=True)
        return Response(events[:limit])


class AdminUserTodosView(AdminReadOnlyAPIView):
    @extend_schema(
        tags=["Admin Dashboard"],
        responses={
            200: TodoSerializer(many=True),
            404: OpenApiResponse(ErrorResponseSerializer),
        },
    )
    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        todos = Todo.objects.filter(
            Q(assigner=user) | Q(assignee=user)
        ).select_related("category", "assigner", "assignee", "team").distinct()
        return Response(TodoSerializer(todos, many=True).data)


class AdminTodoDetailView(AdminReadOnlyAPIView):
    @extend_schema(
        tags=["Admin Dashboard"],
        responses={
            200: TodoSerializer,
            404: OpenApiResponse(ErrorResponseSerializer),
        },
    )
    def get(self, request, todo_id):
        todo = get_object_or_404(
            Todo.objects.select_related("category", "assigner", "assignee", "team"),
            pk=todo_id,
        )
        return Response(TodoSerializer(todo).data)
