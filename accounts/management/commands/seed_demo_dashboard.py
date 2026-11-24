from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from categories.models import Category
from dashboard.models import DashboardSetting
from scrums.models import Scrum
from teams.models import Membership, Team
from todos.models import Todo


class Command(BaseCommand):
    help = "Create a dashboard demo workspace after the database has been flushed."

    def add_arguments(self, parser):
        parser.add_argument("--password", required=True)

    def handle(self, *args, **options):
        password = options["password"]
        now = timezone.now()

        with transaction.atomic():
            teams = {
                name: Team.objects.create(name=name)
                for name in ("Engineering", "Design", "QA")
            }
            categories = {
                name: Category.objects.create(name=name)
                for name in ("Backend", "Frontend", "Bug", "Research", "Operations")
            }

            admin = User.objects.create_user(
                email="demo-admin@example.com",
                password=password,
                name="Demo Admin",
                role=User.Role.ADMIN,
                is_staff=True,
                is_superuser=True,
            )
            Membership.objects.create(user=admin, team=teams["Engineering"])

            members = []
            team_names = ["Engineering"] * 3 + ["Design"] * 3 + ["QA"] * 2
            for index, team_name in enumerate(team_names, start=1):
                member = User.objects.create_user(
                    email=f"demo-user-{index}@example.com",
                    password=password,
                    name=f"Demo User {index}",
                )
                Membership.objects.create(user=member, team=teams[team_name])
                members.append(member)

            scrums = {}
            for team_name, team in teams.items():
                Scrum.objects.create(
                    team=team,
                    name="scrum-1",
                    status=Scrum.Status.ENDED,
                    started_at=now - timedelta(days=120),
                    ended_at=now - timedelta(days=91),
                )
                scrums[team_name] = Scrum.objects.create(
                    team=team,
                    name="scrum-2",
                    status=Scrum.Status.RUNNING,
                    started_at=now - timedelta(days=45),
                )

            settings = DashboardSetting.current()
            settings.overloaded_user_threshold = 5
            settings.overdue_alert_threshold = 2
            settings.save(update_fields=["overloaded_user_threshold", "overdue_alert_threshold"])

            def create_todo(
                title,
                *,
                assigner,
                team,
                scrum,
                category,
                assignee=None,
                status=Todo.Status.PENDING,
                priority=Todo.Priority.MEDIUM,
                assignment_status=None,
                due_date=None,
                created_at=None,
                updated_at=None,
                completed_at=None,
                responded_at=None,
            ):
                todo = Todo.objects.create(
                    title=title,
                    description=f"Demo task for dashboard testing: {title}.",
                    assigner=assigner,
                    team=team,
                    scrum=scrum,
                    category=category,
                    status=status,
                    priority=priority,
                    due_date=due_date,
                )
                if assignee is not None:
                    assigned_at = (created_at or now) - timedelta(hours=4)
                    Todo.objects.filter(pk=todo.pk).update(
                        assignee=assignee,
                        assignment_status=assignment_status or Todo.AssignmentStatus.ACCEPTED,
                        assigned_at=assigned_at,
                        responded_at=responded_at or assigned_at + timedelta(hours=1),
                    )
                updates = {}
                if created_at is not None:
                    updates["created_at"] = created_at
                if updated_at is not None:
                    updates["updated_at"] = updated_at
                if completed_at is not None:
                    updates["completed_at"] = completed_at
                if updates:
                    Todo.objects.filter(pk=todo.pk).update(**updates)
                return todo

            engineering = teams["Engineering"]
            active_scrum = scrums["Engineering"]

            for index in range(1, 21):
                completed_at = now - timedelta(days=(index * 4) % 80)
                create_todo(
                    f"Completed demo task {index}",
                    assigner=members[index % 3],
                    assignee=members[index % 3],
                    team=engineering,
                    scrum=active_scrum,
                    category=categories[("Backend", "Frontend", "Bug")[index % 3]],
                    status=Todo.Status.COMPLETED,
                    priority=(index % 3) + 1,
                    due_date=completed_at + timedelta(days=1 if index % 4 else -1),
                    created_at=completed_at - timedelta(days=3),
                    updated_at=completed_at,
                    completed_at=completed_at,
                )

            for index in range(1, 9):
                create_todo(
                    f"Overloaded active task {index}",
                    assigner=admin,
                    assignee=members[0],
                    team=engineering,
                    scrum=active_scrum,
                    category=categories["Operations"],
                    status=Todo.Status.IN_PROGRESS,
                    priority=Todo.Priority.HIGH if index <= 2 else Todo.Priority.MEDIUM,
                )

            for index in range(1, 4):
                create_todo(
                    f"Unassigned task {index}",
                    assigner=admin,
                    team=engineering,
                    scrum=active_scrum,
                    category=categories["Research"],
                )

            for index in range(1, 5):
                create_todo(
                    f"Overdue task {index}",
                    assigner=admin,
                    assignee=members[1],
                    team=engineering,
                    scrum=active_scrum,
                    category=categories["Bug"],
                    status=Todo.Status.IN_PROGRESS,
                    due_date=now - timedelta(days=index),
                )

            for index in range(1, 5):
                create_todo(
                    f"Rejected task {index}",
                    assigner=admin,
                    assignee=members[3],
                    team=teams["Design"],
                    scrum=scrums["Design"],
                    category=categories["Bug"],
                    assignment_status=Todo.AssignmentStatus.REJECTED,
                )
            create_todo(
                "Accepted comparison task",
                assigner=admin,
                assignee=members[3],
                team=teams["Design"],
                scrum=scrums["Design"],
                category=categories["Frontend"],
                assignment_status=Todo.AssignmentStatus.ACCEPTED,
            )

            inactive_task = create_todo(
                "Inactive user historical task",
                assigner=members[7],
                assignee=members[7],
                team=teams["QA"],
                scrum=scrums["QA"],
                category=categories["Operations"],
                status=Todo.Status.COMPLETED,
                created_at=now - timedelta(days=30),
                updated_at=now - timedelta(days=30),
                completed_at=now - timedelta(days=30),
            )
            Todo.objects.filter(pk=inactive_task.pk).update(
                created_at=now - timedelta(days=30),
                updated_at=now - timedelta(days=30),
                completed_at=now - timedelta(days=30),
            )

        self.stdout.write(self.style.SUCCESS(
            "Demo dashboard data created: demo-admin@example.com and 8 demo users."
        ))
