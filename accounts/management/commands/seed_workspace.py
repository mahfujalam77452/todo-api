import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from teams.models import Membership, Team


class Command(BaseCommand):
    help = "Create the repeatable demo workspace teams, admin, and members."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            dest="password",
            help="Password for seeded users; SEED_PASSWORD is preferred.",
        )

    def handle(self, *args, **options):
        password = options.get("password") or os.environ.get("SEED_PASSWORD")
        if not password:
            if not settings.DEBUG:
                raise CommandError(
                    "Set SEED_PASSWORD or pass --password when DEBUG is false."
                )
            password = "A-safe-password-123!"
            self.stdout.write(self.style.WARNING("Using the local development seed password."))

        teams = {
            "Engineering": Team.objects.get_or_create(name="Engineering")[0],
            "Design": Team.objects.get_or_create(name="Design")[0],
        }

        admin, created = User.objects.get_or_create(
            email="workspace-admin@example.com",
            defaults={
                "name": "Workspace Admin",
                "role": User.Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        changed = []
        if admin.name != "Workspace Admin":
            admin.name = "Workspace Admin"
            changed.append("name")
        if admin.role != User.Role.ADMIN:
            admin.role = User.Role.ADMIN
            changed.append("role")
        if not admin.is_staff:
            admin.is_staff = True
            changed.append("is_staff")
        if not admin.is_superuser:
            admin.is_superuser = True
            changed.append("is_superuser")
        if created or not admin.has_usable_password():
            admin.set_password(password)
            changed.append("password")
        if changed:
            admin.save(update_fields=sorted(set(changed)))
        Membership.objects.update_or_create(user=admin, defaults={"team": teams["Engineering"]})

        members = [
            ("engineering-one@example.com", "Engineering PM", "Engineering", User.Role.PM),
            ("engineering-two@example.com", "Engineering Member 2", "Engineering", User.Role.MEMBER),
            ("design-one@example.com", "Design PM", "Design", User.Role.PM),
            ("design-two@example.com", "Design Member 2", "Design", User.Role.MEMBER),
        ]
        for email, name, team_name, role in members:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"name": name, "role": role},
            )
            changed = []
            if user.name != name:
                user.name = name
                changed.append("name")
            if user.role != role:
                user.role = role
                changed.append("role")
            if created or not user.has_usable_password():
                user.set_password(password)
                changed.append("password")
            if changed:
                user.save(update_fields=sorted(set(changed)))
            Membership.objects.update_or_create(user=user, defaults={"team": teams[team_name]})

        self.stdout.write(self.style.SUCCESS("Workspace seed completed."))
