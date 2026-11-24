from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from activity.reports import teams_with_pm
from activity.tasks import send_team_summary


class Command(BaseCommand):
    help = (
        "Send the daily team summary PDF to the Project Manager(s) right now, "
        "without waiting for midnight. Runs in this process, no worker needed."
    )

    def add_arguments(self, parser):
        parser.add_argument("--date", help="Day to report, YYYY-MM-DD. Default: yesterday.")
        parser.add_argument("--today", action="store_true", help="Report today so far (for testing).")
        parser.add_argument("--team", type=int, help="Only this team id.")
        parser.add_argument("--force", action="store_true", help="Send again even if it was already sent.")

    def handle(self, *args, **options):
        if options["date"]:
            try:
                day = date.fromisoformat(options["date"])
            except ValueError:
                raise CommandError("--date must look like 2026-11-23.")
        elif options["today"]:
            day = timezone.localdate()
        else:
            day = timezone.localdate() - timedelta(days=1)

        team_ids = [options["team"]] if options["team"] else teams_with_pm()
        if not team_ids:
            self.stdout.write(self.style.WARNING("No team has a Project Manager."))
            return
        for team_id in team_ids:
            result = send_team_summary(team_id, day.isoformat(), options["force"])
            self.stdout.write(f"team {team_id}: {result}")