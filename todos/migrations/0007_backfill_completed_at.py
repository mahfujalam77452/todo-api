from django.db import migrations
from django.utils import timezone


def backfill_completed_at(apps, schema_editor):
    Todo = apps.get_model("todos", "Todo")
    Todo.objects.filter(status="completed", completed_at__isnull=True).update(
        completed_at=timezone.now()
    )


class Migration(migrations.Migration):
    dependencies = [("todos", "0006_scrum_completion")]
    operations = [
        migrations.RunPython(backfill_completed_at, migrations.RunPython.noop),
    ]
