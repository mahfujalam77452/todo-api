"""Demo data to try every feature of the app without clicking around first.

    python manage.py seed_demo_data

It works alone and also after `seed_demo_dashboard` (same teams are reused).
Safe to run again: it first removes the todos, activity, notifications and bulk
emails it created, then creates them again. It never deletes the todos made by
`seed_demo_dashboard`. No email is sent.
"""
import os
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from activity.models import ActivityLog, BulkEmail, DailySummary
from categories.models import Category
from notifications.models import Notification
from scrums.models import Scrum
from teams.models import Membership, Team
from todos.models import Todo

A = ActivityLog.Action
S = Todo.Status
AS = Todo.AssignmentStatus

# email, name, team, role
PEOPLE = [
    ("demo-admin@example.com", "Demo Admin", "Engineering", User.Role.ADMIN),
    ("engineering-one@example.com", "Farhan Chowdhury", "Engineering", User.Role.PM),
    ("engineering-two@example.com", "Rafi Ahmed", "Engineering", User.Role.MEMBER),
    ("engineering-three@example.com", "Nusrat Jahan", "Engineering", User.Role.MEMBER),
    ("engineering-four@example.com", "Tanvir Hasan", "Engineering", User.Role.MEMBER),
    ("design-one@example.com", "Sadia Islam", "Design", User.Role.PM),
    ("design-two@example.com", "Imran Hossain", "Design", User.Role.MEMBER),
    ("design-three@example.com", "Maliha Khan", "Design", User.Role.MEMBER),
    # Marketing has NO Project Manager: shows that no action mail is sent there.
    ("marketing-one@example.com", "Kamal Uddin", "Marketing", User.Role.MEMBER),
    ("marketing-two@example.com", "Lamia Akter", "Marketing", User.Role.MEMBER),
    # A person without a team.
    ("no-team@example.com", "Unassigned User", None, User.Role.MEMBER),
]
ADMIN_EMAIL = "demo-admin@example.com"
# The admin also exists in seed_demo_dashboard, whose todos must stay. So only
# these admin-made todos (by title) are removed when this command runs again.
ADMIN_TODO_TITLES = ["Prepare the release notes"]
TEAMS = ["Engineering", "Design", "Marketing"]
CATEGORIES = ["Bug", "Feature", "Documentation", "Design", "Marketing", "Planning"]


def get_or_create_by_name(model, name):
    """Find by name ignoring case (the unique rules ignore case), else create."""
    return model.objects.filter(name__iexact=name).first() or model.objects.create(name=name)


class Command(BaseCommand):
    help = "Create demo users, teams, todos, activity and bulk emails to test every feature."

    def add_arguments(self, parser):
        parser.add_argument("--password", help="Password for demo users; SEED_PASSWORD is preferred.")

    # ------------------------------------------------------------------ main
    def handle(self, *args, **options):
        password = options.get("password") or os.environ.get("SEED_PASSWORD")
        if not password:
            if not settings.DEBUG:
                raise CommandError("Set SEED_PASSWORD or pass --password when DEBUG is false.")
            password = "A-safe-password-123!"

        self.now = timezone.now()
        with transaction.atomic():
            self.teams = {name: get_or_create_by_name(Team, name) for name in TEAMS}
            self.users = self.make_users(password)
            self.cats = {n: get_or_create_by_name(Category, n) for n in CATEGORIES}
            self.running_scrums = self.ensure_running_scrums()
            self.clear_old_demo_data()
            self.engineering()
            self.design()
            self.marketing()
            self.bulk_emails()

        self.report(password)

    # ----------------------------------------------------------------- users
    def make_users(self, password):
        users = {}
        for email, name, team_name, role in PEOPLE:
            user, created = User.objects.get_or_create(email=email, defaults={"name": name})
            user.name = name
            user.role = User.Role.MEMBER  # promoted below, after the team is set
            if role == User.Role.ADMIN:
                user.role, user.is_staff, user.is_superuser = User.Role.ADMIN, True, True
            if created or not user.has_usable_password():
                user.set_password(password)
            user.save()
            if team_name:
                Membership.objects.update_or_create(user=user, defaults={"team": self.teams[team_name]})
            else:
                Membership.objects.filter(user=user).delete()
            users[email.split("@")[0]] = user

        # One Project Manager per team: demote any other PM first, then promote.
        for email, name, team_name, role in PEOPLE:
            if role != User.Role.PM:
                continue
            User.objects.filter(
                role=User.Role.PM, membership__team=self.teams[team_name]
            ).exclude(email=email).update(role=User.Role.MEMBER)
            User.objects.filter(email=email).update(role=User.Role.PM)
            users[email.split("@")[0]].refresh_from_db()
        return users

    def ensure_running_scrums(self):
        """Every demo team gets a running Scrum (reuse the one that already exists)."""
        running = {}
        for name, team in self.teams.items():
            scrum = Scrum.objects.filter(team=team, status=Scrum.Status.RUNNING).first()
            if scrum is None:
                scrum = Scrum.objects.create(
                    team=team,
                    name=f"scrum-{team.scrums.count() + 1}",
                    status=Scrum.Status.RUNNING,
                    started_at=self.now - timedelta(days=14),
                )
            running[name] = scrum
        return running

    def clear_old_demo_data(self):
        # Not the admin: seed_demo_dashboard's todos belong to the same admin.
        people = [u for u in self.users.values() if u.email != ADMIN_EMAIL]
        teams = list(self.teams.values())
        ActivityLog.objects.filter(team__in=teams).delete()
        BulkEmail.objects.filter(team__in=teams).delete()
        DailySummary.objects.filter(team__in=teams).delete()
        Notification.objects.filter(recipient__in=people).delete()
        Todo.objects.filter(Q(assigner__in=people) | Q(assignee__in=people)).delete()
        Todo.objects.filter(
            assigner__email=ADMIN_EMAIL, title__in=ADMIN_TODO_TITLES
        ).delete()

    # --------------------------------------------------------------- helpers
    def moment(self, day, hour, minute=0):
        """A time on a day (0 = today, -1 = yesterday ...), in the project time zone.

        For today the hour is scaled to the time that has passed so far, so a
        seed run at 09:00 never creates actions in the future.
        """
        start = timezone.make_aware(
            datetime.combine(timezone.localdate() + timedelta(days=day), time.min)
        )
        if day == 0:
            return start + (self.now - start) * ((hour * 60 + minute) / (24 * 60))
        return start + timedelta(hours=hour, minutes=minute)

    def todo(self, assigner, assignee=None, *, title, at, team=None, status=S.PENDING,
             priority=2, due=None, cat=None, answer=None, answered_at=None, description=""):
        assigner = self.users[assigner]
        assignee = self.users[assignee] if assignee else None
        todo = Todo.objects.create(
            title=title,
            description=description,
            status=status,
            priority=priority,
            due_date=due,
            category=self.cats.get(cat),
            assigner=assigner,
            assignee=assignee,
            team=self.teams[team] if team else None,
            scrum=self.running_scrums[team] if team else None,
            assignment_status=(answer or AS.PENDING) if assignee else None,
            assigned_at=at if assignee else None,
            responded_at=answered_at if assignee and answer in (AS.ACCEPTED, AS.REJECTED) else None,
        )
        # Todo.save() stamps "now": put the real dates back (completed_at feeds the dashboard).
        Todo.objects.filter(pk=todo.pk).update(
            created_at=at,
            updated_at=answered_at or at,
            completed_at=(answered_at or at) if status == S.COMPLETED else None,
        )
        return todo

    def log(self, team, actor, action, todo, at, **details):
        """One activity row. `pm_notified_at` is set as if the PM email had gone out."""
        team_obj = self.teams[team]
        actor_obj = self.users[actor]
        pm_gets_mail = (
            actor_obj.role != User.Role.PM
            and User.objects.filter(role=User.Role.PM, membership__team=team_obj).exists()
        )
        row = ActivityLog.objects.create(
            team=team_obj,
            actor=actor_obj,
            actor_name=actor_obj.name,
            action=action,
            todo=todo,
            todo_title=todo.title,
            details=details,
        )
        ActivityLog.objects.filter(pk=row.pk).update(
            created_at=at, pm_notified_at=at + timedelta(minutes=1) if pm_gets_mail else None
        )

    def notify(self, todo, recipient, kind, message, at, read=False):
        row = Notification.objects.create(
            recipient=self.users[recipient], type=kind, message=message,
            todo=todo, link=f"/todos/{todo.pk}", is_read=read,
            read_at=at if read else None,
        )
        Notification.objects.filter(pk=row.pk).update(created_at=at)

    def assigned_flow(self, team, assigner, assignee, *, title, day, hour, answer=AS.ACCEPTED,
                      reason=None, **kwargs):
        """created+assigned -> answer, with logs and notifications. Returns the todo."""
        created = self.moment(day, hour)
        answered = self.moment(day, hour, 40) if answer != AS.PENDING else None
        todo = self.todo(assigner, assignee, title=title, at=created, team=team,
                         answer=answer, answered_at=answered, **kwargs)
        who = self.users[assignee].name
        self.log(team, assigner, A.CREATED, todo, created, assignee=who)
        self.notify(todo, assignee, Notification.Type.ASSIGNED,
                    f"{self.users[assigner].name} assigned you: {title}", created,
                    read=answer != AS.PENDING)
        if answer == AS.ACCEPTED:
            self.log(team, assignee, A.ACCEPTED, todo, answered)
            self.notify(todo, assigner, Notification.Type.ACCEPTED,
                        f"{who} accepted: {title}", answered, read=True)
        elif answer == AS.REJECTED:
            self.log(team, assignee, A.REJECTED, todo, answered, reason=reason or "")
            self.notify(todo, assigner, Notification.Type.REJECTED,
                        f"{who} rejected: {title}" + (f" ({reason})" if reason else ""),
                        answered)
        return todo

    def change(self, team, actor, todo, at, **changes):
        """Update a todo and log the change as {"field": [old, new]}."""
        diff = {}
        for field, new in changes.items():
            diff[field] = [getattr(todo, field), new]
            setattr(todo, field, new)
        todo.save()
        extra = {"updated_at": at}
        if "status" in changes:
            extra["completed_at"] = at if changes["status"] == S.COMPLETED else None
        Todo.objects.filter(pk=todo.pk).update(**extra)
        self.log(team, actor, A.UPDATED, todo, at, changes=diff)

    # ------------------------------------------------------------- scenarios
    def engineering(self):
        T = "Engineering"
        # Two days ago: a little history, so "vs the day before" has a number.
        old = self.assigned_flow(T, "engineering-two", "engineering-three", day=-2, hour=10,
                                 title="Draft the release checklist", cat="Planning")
        self.change(T, "engineering-three", old, self.moment(-2, 15), status=S.COMPLETED)
        self.assigned_flow(T, "engineering-three", "engineering-four", day=-2, hour=11,
                           title="Review the security checklist", cat="Planning",
                           answer=AS.PENDING)  # never answered: shows up as "waiting"

        # Yesterday: the day the nightly PDF is about.
        bug = self.assigned_flow(T, "engineering-two", "engineering-three", day=-1, hour=9,
                                 title="Fix the login redirect bug", priority=3, cat="Bug",
                                 description="After login the user lands on a blank page.")
        self.change(T, "engineering-three", bug, self.moment(-1, 10, 5), status=S.IN_PROGRESS)
        self.change(T, "engineering-three", bug, self.moment(-1, 16, 20), status=S.COMPLETED)

        self.assigned_flow(T, "engineering-three", "engineering-four", day=-1, hour=10,
                           title="Write API docs for the notification endpoints",
                           cat="Documentation", answer=AS.REJECTED,
                           reason="Blocked until the auth refactor is merged")

        ci = self.assigned_flow(T, "engineering-four", "engineering-two", day=-1, hour=11,
                                title="Set up the CI cache", priority=2, cat="Feature")
        self.change(T, "engineering-two", ci, self.moment(-1, 15), priority=3)

        road = self.todo("engineering-two", title="Plan the Q1 roadmap", at=self.moment(-1, 14),
                         team=T, cat="Planning", priority=2)
        self.log(T, "engineering-two", A.CREATED, road, self.moment(-1, 14))
        self.change(T, "engineering-two", road, self.moment(-1, 14, 30),
                    due_date=(self.now + timedelta(days=14)).isoformat())

        spike = self.todo("engineering-four", title="Spike: websocket notifications",
                          at=self.moment(-1, 13), team=T)
        self.log(T, "engineering-four", A.CREATED, spike, self.moment(-1, 13))
        self.log(T, "engineering-four", A.DELETED, spike, self.moment(-1, 17, 30))
        spike.delete()

        # The PM's own work (never mailed to the PM, but it is in the report).
        self.assigned_flow(T, "engineering-one", "engineering-three", day=-1, hour=12,
                           title="Review the sprint scope", cat="Planning", priority=2)
        self.assigned_flow(T, "demo-admin", "engineering-two", day=-1, hour=17,
                           title="Prepare the release notes", cat="Documentation",
                           answer=AS.PENDING)

        # Open work that is late right now ("Needs attention" in the PDF).
        self.assigned_flow(T, "engineering-three", "engineering-two", day=-4, hour=9,
                           title="Migrate the staging database", priority=3, cat="Bug",
                           status=S.IN_PROGRESS, due=self.now - timedelta(days=3))
        self.assigned_flow(T, "engineering-two", "engineering-four", day=-3, hour=14,
                           title="Update the dependency versions", cat="Feature",
                           due=self.now - timedelta(days=1))

        # Today: the "--today" report and the live inbox.
        flaky = self.assigned_flow(T, "engineering-three", "engineering-two", day=0, hour=8,
                                   title="Fix the flaky tests", priority=3, cat="Bug",
                                   due=self.now + timedelta(days=2))
        self.change(T, "engineering-two", flaky, self.moment(0, 14), status=S.IN_PROGRESS)
        self.assigned_flow(T, "engineering-four", "engineering-three", day=0, hour=10,
                           title="Add rate limiting to the bulk mail API", cat="Feature",
                           answer=AS.PENDING, priority=2)
        solo = self.todo("engineering-four", title="Clean up old feature flags",
                         at=self.moment(0, 6), team=T, cat="Planning")
        self.log(T, "engineering-four", A.CREATED, solo, self.moment(0, 6))

    def design(self):
        T = "Design"
        self.assigned_flow(T, "design-three", "design-two", day=-2, hour=10,
                           title="Icon set refresh", cat="Design", answer=AS.PENDING)
        onboarding = self.assigned_flow(T, "design-two", "design-three", day=-1, hour=9,
                                        title="Design the onboarding screens", priority=3, cat="Design")
        self.change(T, "design-three", onboarding, self.moment(-1, 15), status=S.COMPLETED)
        self.assigned_flow(T, "design-three", "design-two", day=-1, hour=11,
                           title="Prepare the usability test script", cat="Planning",
                           answer=AS.REJECTED, reason="I am on leave next week")
        self.assigned_flow(T, "design-one", "design-three", day=-1, hour=13,
                           title="Review the colour palette", cat="Design")
        self.assigned_flow(T, "design-two", "design-three", day=-3, hour=9,
                           title="Brand guideline PDF", cat="Documentation", priority=3,
                           due=self.now - timedelta(days=2), status=S.IN_PROGRESS)
        self.assigned_flow(T, "design-three", "design-two", day=0, hour=9,
                           title="Landing page hero image", cat="Design")

    def marketing(self):
        T = "Marketing"  # no Project Manager: actions are logged, nobody is mailed
        self.assigned_flow(T, "marketing-one", "marketing-two", day=-1, hour=10,
                           title="Write the newsletter draft", cat="Marketing")
        self.assigned_flow(T, "marketing-two", "marketing-one", day=0, hour=9,
                           title="Plan the launch post", cat="Marketing", answer=AS.PENDING)
        # A todo from the person without a team (personal, not assigned).
        self.todo("no-team", title="My personal todo", at=self.moment(-1, 9), cat="Planning")

    def bulk_emails(self):
        def make(sender, team, subject, message, day, hour):
            people = Membership.objects.filter(team=self.teams[team]).exclude(
                user=self.users[sender]).count()
            at = self.moment(day, hour)
            row = BulkEmail.objects.create(
                team=self.teams[team], sender=self.users[sender],
                sender_name=self.users[sender].name, subject=subject, message=message,
                recipient_count=people, sent_count=people, failed_count=0, sent_at=at,
            )
            BulkEmail.objects.filter(pk=row.pk).update(created_at=at)

        make("engineering-one", "Engineering", "Sprint planning moved to Thursday",
             "Hi team,\n\nSprint planning moves to Thursday 10:00.\nPlease update your todos before then.\n\nThanks, Farhan",
             -1, 18)
        make("engineering-one", "Engineering", "Please update your todo statuses",
             "A reminder: keep your todo statuses current. I read them every morning.", 0, 9)
        make("design-one", "Design", "Design review on Friday",
             "Design review is on Friday at 15:00. Bring your latest screens.", -1, 16)

    # ---------------------------------------------------------------- output
    def report(self, password):
        out = self.stdout
        out.write(self.style.SUCCESS("Demo data created."))
        out.write("")
        out.write(f"All demo users use the password: {password}")
        out.write("")
        out.write(f"  {'EMAIL':<34}{'ROLE':<10}TEAM")
        for email, name, team, role in PEOPLE:
            out.write(f"  {email:<34}{role:<10}{team or '(no team)'}")
        out.write("")
        out.write("Try next:")
        out.write("  python manage.py send_daily_summary --force          # yesterday's PDF (what midnight sends)")
        out.write("  python manage.py send_daily_summary --today --force  # today so far")
        out.write("  Log in as engineering-two@ and do something: Farhan (Engineering PM) gets a mail.")
        out.write("  Log in as engineering-one@ (PM) and open Team mail to email the team.")
        out.write("  Marketing has no PM: actions there are logged but nobody is mailed.")
        out.write("  Teams Engineering/Design/Marketing each have a running Scrum.")