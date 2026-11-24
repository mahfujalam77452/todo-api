from datetime import timedelta
from django.db import models, transaction
from django.db.models.functions import TruncDate, TruncWeek
from django.core.exceptions import ValidationError as DjangoValidationError

from django.contrib.auth import get_user_model
from django.db.models import Count, Exists, OuterRef, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiResponse, extend_schema

from core.permissions import IsAdminRole
from core.schema import ErrorResponseSerializer
from todos.models import Todo
from todos.serializers import TodoSerializer
from teams.models import Membership, Team
from scrums.models import Scrum
from .models import DashboardSetting, OverdueAlert
from .serializers_scrums import ScrumSerializer
from .serializers_settings import DashboardSettingSerializer

from .serializers import (
    ActivitySerializer,
    DashboardTeamSerializer,
    DashboardUserSerializer,
    OverviewSerializer,
)

User = get_user_model()
TASK_ACTIVITY_DAYS = 14


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


def _user_rows(since=None):
    assigned_filter = Q(assigned_todos__isnull=False)
    created_filter = Q(created_todos__isnull=False)
    if since is not None:
        assigned_filter &= Q(assigned_todos__created_at__gte=since)
        created_filter &= Q(created_todos__created_at__gte=since)
    return User.objects.select_related("membership__team").annotate(
        created_count=Count("created_todos", filter=created_filter, distinct=True),
        assigned_count=Count("assigned_todos", filter=assigned_filter, distinct=True),
        completed_count=Count(
            "assigned_todos",
            filter=assigned_filter & Q(assigned_todos__status=Todo.Status.COMPLETED),
            distinct=True,
        ),
        rejected_count=Count(
            "assigned_todos",
            filter=assigned_filter & Q(
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
        period_start = now - timedelta(days=TASK_ACTIVITY_DAYS)
        period_todos = Todo.objects.filter(created_at__gte=period_start)
        total_todos = period_todos.count()
        completed_todos = period_todos.filter(status=Todo.Status.COMPLETED).count()
        pending_assignments = period_todos.filter(
            assignment_status=Todo.AssignmentStatus.PENDING
        ).count()
        pending_seven_days = period_todos.filter(
            assignment_status=Todo.AssignmentStatus.PENDING,
            assigned_at__isnull=False,
            assigned_at__lte=now - timedelta(days=7),
        ).count()
        overdue = period_todos.filter(
            due_date__isnull=False,
            due_date__lt=now,
        ).exclude(status=Todo.Status.COMPLETED).count()
        active_scope = period_todos.filter(scrum__status=Scrum.Status.RUNNING)
        dashboard_settings = DashboardSetting.current()
        overloaded = active_scope.filter(
            assignee__isnull=False,
            status__in=[Todo.Status.PENDING, Todo.Status.IN_PROGRESS],
        ).values("assignee_id", "assignee__name").annotate(
            active_count=Count("id")
        ).filter(
            active_count__gt=dashboard_settings.overloaded_user_threshold
        ).order_by("-active_count", "assignee__name")
        recent_activity = Todo.objects.filter(
            Q(assigner_id=OuterRef("pk")) | Q(assignee_id=OuterRef("pk")),
            updated_at__gte=now - timedelta(days=TASK_ACTIVITY_DAYS),
        )
        inactive_users = User.objects.filter(
            is_active=True
        ).annotate(
            has_recent_task_activity=Exists(recent_activity)
        ).filter(
            has_recent_task_activity=False
        ).values("id", "name", "email")

        rejected_users = [
            {
                "id": user.pk,
                "name": user.name,
                "rejection_rate": _percentage(
                    user.rejected_count, user.assigned_count
                ),
            }
            for user in _user_rows(period_start).order_by("-rejected_count", "email")
            if user.rejected_count and _percentage(
                user.rejected_count, user.assigned_count
            ) >= 50
        ][:10]

        overdue_alert_count = active_scope.filter(due_date__lt=now).exclude(
            status=Todo.Status.COMPLETED
        ).count()
        overdue_alert, created = OverdueAlert.objects.get_or_create(
            scope_key="active-scrums",
            defaults={
                "overdue_count": overdue_alert_count,
                "threshold": dashboard_settings.overdue_alert_threshold,
                "is_active": overdue_alert_count > dashboard_settings.overdue_alert_threshold,
            },
        )
        if not created:
            overdue_alert.overdue_count = overdue_alert_count
            overdue_alert.threshold = dashboard_settings.overdue_alert_threshold
            overdue_alert.is_active = overdue_alert_count > overdue_alert.threshold
            overdue_alert.resolved_at = None if overdue_alert.is_active else (
                overdue_alert.resolved_at or now
            )
            overdue_alert.save(update_fields=[
                "overdue_count", "threshold", "is_active", "resolved_at"
            ])

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
                    "unassigned_todos": active_scope.filter(assignee__isnull=True).count(),
                    "overloaded_users": [
                        {"id": row["assignee_id"], "name": row["assignee__name"], "active_count": row["active_count"]}
                        for row in overloaded
                    ],
                    "overloaded_threshold": dashboard_settings.overloaded_user_threshold,
                    "inactive_users": list(inactive_users),
                    "overdue_alert": {
                        "id": overdue_alert.pk,
                        "count": overdue_alert_count,
                        "threshold": dashboard_settings.overdue_alert_threshold,
                        "active": overdue_alert.is_active,
                        "created_at": overdue_alert.created_at,
                        "resolved_at": overdue_alert.resolved_at,
                    },
                    "reporting_period": {
                        "from": period_start.date(),
                        "to": now.date(),
                        "days": 14,
                    },
                },
            }
        )


class DashboardUsersView(AdminReadOnlyAPIView):
    @extend_schema(
        tags=["Admin Dashboard"],
        responses={200: DashboardUserSerializer(many=True)},
    )
    def get(self, request):
        queryset = _user_rows(
            timezone.now() - timedelta(days=TASK_ACTIVITY_DAYS)
        ).order_by("email")
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
        period_start = timezone.now() - timedelta(days=TASK_ACTIVITY_DAYS)
        teams = Team.objects.annotate(
            member_count=Count("memberships", distinct=True),
            todo_count=Count(
                "todos",
                filter=Q(todos__created_at__gte=period_start),
                distinct=True,
            ),
            completed_count=Count(
                "todos",
                filter=Q(
                    todos__created_at__gte=period_start,
                    todos__status=Todo.Status.COMPLETED,
                ),
                distinct=True,
            ),
            pending_assignment_count=Count(
                "todos",
                filter=Q(
                    todos__created_at__gte=period_start,
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

        todos = Todo.objects.filter(
            updated_at__gte=timezone.now() - timedelta(days=TASK_ACTIVITY_DAYS)
        ).select_related("assigner", "assignee").order_by(
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


def _filtered_admin_todos(request, *, default_active=True, apply_relation=True):
    todos = Todo.objects.select_related(
        "category", "assigner", "assignee", "team", "scrum"
    )
    team_id = request.query_params.get("team")
    scrum_id = request.query_params.get("scrum")
    user_id = request.query_params.get("user")
    category_id = request.query_params.get("category")
    relation = request.query_params.get("relation")
    if team_id:
        todos = todos.filter(team_id=team_id)
    if scrum_id:
        if not str(scrum_id).isdigit() or not Scrum.objects.filter(pk=scrum_id).exists():
            raise ValueError("scrum must be a valid Scrum id.")
        todos = todos.filter(scrum_id=scrum_id)
    elif default_active:
        active_scrums = Scrum.objects.filter(status=Scrum.Status.RUNNING)
        if team_id:
            active_scrums = active_scrums.filter(team_id=team_id)
        elif user_id:
            active_scrums = active_scrums.filter(
                team__memberships__user_id=user_id
            )
        todos = todos.filter(scrum__in=active_scrums)
    if user_id:
        todos = todos.filter(Q(assigner_id=user_id) | Q(assignee_id=user_id))
        if apply_relation and relation == "assigned":
            todos = todos.filter(assignee_id=user_id)
        elif apply_relation and relation == "created":
            todos = todos.filter(assigner_id=user_id)
    if relation and relation not in {"assigned", "created"}:
        raise ValueError("relation must be assigned or created.")
    if category_id:
        if not str(category_id).isdigit():
            raise ValueError("category must be a valid category id.")
        todos = todos.filter(category_id=category_id)
    if request.query_params.get("status"):
        todos = todos.filter(status=request.query_params["status"].strip().lower())
    if request.query_params.get("from"):
        start = parse_date(request.query_params["from"])
        if start is None:
            raise ValueError("from must be a valid date in YYYY-MM-DD format.")
        todos = todos.filter(created_at__date__gte=start)
    if request.query_params.get("to"):
        end = parse_date(request.query_params["to"])
        if end is None:
            raise ValueError("to must be a valid date in YYYY-MM-DD format.")
        todos = todos.filter(created_at__date__lte=end)
    return todos.distinct()


def _todo_stats(todos):
    completed = todos.filter(status=Todo.Status.COMPLETED)
    accepted = todos.filter(assignment_status=Todo.AssignmentStatus.ACCEPTED)
    rejected = todos.filter(assignment_status=Todo.AssignmentStatus.REJECTED)
    response_times = [
        (todo.responded_at - todo.assigned_at).total_seconds()
        for todo in todos
        if todo.assigned_at and todo.responded_at
    ]
    return {
        "completed": completed.count(),
        "completed_high": completed.filter(priority=Todo.Priority.HIGH).count(),
        "completed_medium": completed.filter(priority=Todo.Priority.MEDIUM).count(),
        "completed_low": completed.filter(priority=Todo.Priority.LOW).count(),
        "accepted": accepted.count(),
        "rejected": rejected.count(),
        "average_response_time_seconds": round(sum(response_times) / len(response_times), 2)
        if response_times else 0,
        "completed_on_time": completed.filter(
            due_date__isnull=False, completed_at__lte=models.F("due_date")
        ).count(),
        "completed_overdue": completed.filter(
            due_date__isnull=False, completed_at__gt=models.F("due_date")
        ).count(),
    }


class AdminScrumListView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        queryset = Scrum.objects.select_related("team")
        if request.query_params.get("team"):
            queryset = queryset.filter(team_id=request.query_params["team"])
        return Response(ScrumSerializer(queryset, many=True).data)

    def post(self, request):
        serializer = ScrumSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            team = get_object_or_404(
                Team.objects.select_for_update(), pk=serializer.validated_data["team"].pk
            )
            number = team.scrums.count() + 1
            while team.scrums.filter(name=f"scrum-{number}").exists():
                number += 1
            scrum = Scrum.objects.create(team=team, name=f"scrum-{number}")
        return Response(ScrumSerializer(scrum).data, status=201)


class AdminScrumStartView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request, scrum_id):
        with transaction.atomic():
            scrum = get_object_or_404(
                Scrum.objects.select_for_update().select_related("team"), pk=scrum_id
            )
            if scrum.status == Scrum.Status.ENDED:
                return Response(
                    {"error": "A finished Scrum cannot be started again.", "code": 409},
                    status=409,
                )
            now = timezone.now()
            Scrum.objects.filter(team=scrum.team, status=Scrum.Status.RUNNING).exclude(
                pk=scrum.pk
            ).update(status=Scrum.Status.ENDED, ended_at=now)
            scrum.status = Scrum.Status.RUNNING
            scrum.started_at = scrum.started_at or now
            scrum.ended_at = None
            scrum.save(update_fields=["status", "started_at", "ended_at"])
            Todo.objects.filter(
                team=scrum.team,
                scrum__isnull=True,
                status__in=[Todo.Status.PENDING, Todo.Status.IN_PROGRESS],
            ).update(scrum=scrum)
        return Response(ScrumSerializer(scrum).data)


class AdminScrumEndView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request, scrum_id):
        with transaction.atomic():
            scrum = get_object_or_404(
                Scrum.objects.select_for_update().select_related("team"), pk=scrum_id
            )
            if scrum.status != Scrum.Status.RUNNING:
                return Response(
                    {"error": "Only an active Scrum can be ended.", "code": 409},
                    status=409,
                )
            scrum.status = Scrum.Status.ENDED
            scrum.ended_at = timezone.now()
            scrum.save(update_fields=["status", "ended_at"])
        return Response(ScrumSerializer(scrum).data)


class AdminDashboardSettingsView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        return Response(DashboardSettingSerializer(DashboardSetting.current()).data)

    def patch(self, request):
        setting = DashboardSetting.current()
        serializer = DashboardSettingSerializer(setting, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AdminTodoHistoryView(AdminReadOnlyAPIView):
    def get(self, request):
        try:
            todos = _filtered_admin_todos(request)
            performance_todos = todos
            user_id = request.query_params.get("user")
            if user_id:
                performance_todos = _filtered_admin_todos(
                    request, apply_relation=False
                ).filter(assignee_id=user_id)
        except ValueError as error:
            return Response({"error": str(error), "code": 400}, status=400)
        try:
            limit = min(max(int(request.query_params.get("limit", 100)), 1), 500)
        except ValueError:
            return Response({"error": "limit must be an integer.", "code": 400}, status=400)
        return Response({
            "todos": TodoSerializer(todos.order_by("-created_at", "-id")[:limit], many=True).data,
            "statistics": _todo_stats(performance_todos),
            "filters": {
                "scrum": request.query_params.get("scrum"),
                "team": request.query_params.get("team"),
                "user": request.query_params.get("user"),
                "category": request.query_params.get("category"),
                "from": request.query_params.get("from"),
                "to": request.query_params.get("to"),
                "relation": request.query_params.get("relation"),
            },
        })


class AdminBottleneckTodosView(AdminReadOnlyAPIView):
    def get(self, request, kind):
        now = timezone.now()
        period_start = now - timedelta(days=TASK_ACTIVITY_DAYS)
        todos = Todo.objects.filter(
            created_at__gte=period_start
        ).select_related("category", "assigner", "assignee", "team", "scrum")
        if kind == "unassigned":
            todos = todos.filter(
                assignee__isnull=True,
                scrum__status=Scrum.Status.RUNNING,
            )
        elif kind == "overdue":
            todos = todos.filter(due_date__lt=now).exclude(status=Todo.Status.COMPLETED)
        elif kind == "pending-assignments":
            todos = todos.filter(
                assignment_status=Todo.AssignmentStatus.PENDING,
                assigned_at__lte=now - timedelta(days=7),
            )
        elif kind == "high-rejection":
            rejection_rows = todos.filter(
                assignee__isnull=False,
                assignment_status__in=[
                    Todo.AssignmentStatus.ACCEPTED,
                    Todo.AssignmentStatus.REJECTED,
                ],
            ).values("assignee_id").annotate(
                total=Count("id"),
                rejected=Count(
                    "id",
                    filter=Q(
                        assignment_status=Todo.AssignmentStatus.REJECTED
                    ),
                ),
            )
            high_rejection_ids = [
                row["assignee_id"]
                for row in rejection_rows
                if row["rejected"] / row["total"] >= 0.5
            ]
            todos = todos.filter(assignee_id__in=high_rejection_ids)
        elif kind == "overloaded":
            threshold = DashboardSetting.current().overloaded_user_threshold
            overloaded_ids = todos.filter(
                assignee__isnull=False,
                status__in=[Todo.Status.PENDING, Todo.Status.IN_PROGRESS],
                scrum__status=Scrum.Status.RUNNING,
            ).values("assignee_id").annotate(
                active_count=Count("id")
            ).filter(active_count__gt=threshold).values_list("assignee_id", flat=True)
            todos = todos.filter(assignee_id__in=overloaded_ids).filter(
                status__in=[Todo.Status.PENDING, Todo.Status.IN_PROGRESS]
            )
        elif kind == "inactive":
            cutoff = now - timedelta(days=TASK_ACTIVITY_DAYS)
            recent_activity = Todo.objects.filter(
                Q(assigner_id=OuterRef("pk")) | Q(assignee_id=OuterRef("pk")),
                updated_at__gte=cutoff,
            )
            inactive_ids = User.objects.filter(
                is_active=True
            ).annotate(
                has_recent_task_activity=Exists(recent_activity)
            ).filter(
                has_recent_task_activity=False
            ).values("id")
            todos = Todo.objects.filter(
                Q(assigner_id__in=inactive_ids) | Q(assignee_id__in=inactive_ids),
                created_at__gte=period_start,
            ).select_related("category", "assigner", "assignee", "team", "scrum")
        else:
            return Response({"error": "Unknown bottleneck.", "code": 400}, status=400)
        return Response(TodoSerializer(todos.order_by("-created_at", "-id"), many=True).data)


class AdminTeamAnalyticsView(AdminReadOnlyAPIView):
    def get(self, request, team_id):
        six_months_ago = timezone.now() - timedelta(days=183)
        creation_todos = Todo.objects.filter(
            team_id=team_id, created_at__gte=six_months_ago
        ).select_related("scrum")
        completion_todos = Todo.objects.filter(
            team_id=team_id,
            status=Todo.Status.COMPLETED,
            completed_at__gte=six_months_ago,
        ).select_related("scrum")
        scrum_id = request.query_params.get("scrum")
        if scrum_id:
            if not Scrum.objects.filter(pk=scrum_id, team_id=team_id).exists():
                return Response(
                    {"error": "scrum must belong to the selected team.", "code": 400},
                    status=400,
                )
            creation_todos = creation_todos.filter(scrum_id=scrum_id)
            completion_todos = completion_todos.filter(scrum_id=scrum_id)
        creation = creation_todos.annotate(day=TruncDate("created_at")).values("day").annotate(
            count=Count("id")
        ).order_by("day")
        completion = completion_todos.annotate(
            week=TruncWeek("completed_at")
        ).values("week").annotate(count=Count("id")).order_by("week")
        return Response({
            "team": team_id,
            "scrum": scrum_id,
            "task_creation": [{"date": row["day"], "count": row["count"]} for row in creation],
            "velocity": [{"week": row["week"], "count": row["count"]} for row in completion],
        })


class AdminCompletionHeatmapView(AdminReadOnlyAPIView):
    def get(self, request):
        end = timezone.localdate()
        start = end - timedelta(days=89)
        queryset = Todo.objects.filter(
            status=Todo.Status.COMPLETED,
            completed_at__date__gte=start,
            completed_at__date__lte=end,
        )
        rows = queryset.annotate(day=TruncDate("completed_at")).values("day").annotate(
            count=Count("id")
        ).order_by("day")
        counts = {row["day"]: row["count"] for row in rows}
        return Response([
            {
                "date": start + timedelta(days=offset),
                "weekday": (start + timedelta(days=offset)).weekday(),
                "count": counts.get(start + timedelta(days=offset), 0),
            }
            for offset in range(90)
        ])
