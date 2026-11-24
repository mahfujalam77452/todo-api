from django.db import migrations, models


def migrate_statuses(apps, schema_editor):
    Scrum = apps.get_model("scrums", "Scrum")
    Scrum.objects.filter(status="active").update(status="running")
    Scrum.objects.filter(status="completed").update(status="ended")
    Scrum.objects.filter(status__isnull=True).update(status="created")


def reverse_statuses(apps, schema_editor):
    Scrum = apps.get_model("scrums", "Scrum")
    Scrum.objects.filter(status="running").update(status="active")
    Scrum.objects.filter(status="ended").update(status="completed")
    Scrum.objects.filter(status="created").update(status="completed")


class Migration(migrations.Migration):
    dependencies = [
        ("scrums", "0001_initial"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="scrum",
            name="one_active_scrum_per_team",
        ),
        migrations.RunPython(migrate_statuses, reverse_statuses),
        migrations.AlterField(
            model_name="scrum",
            name="status",
            field=models.CharField(
                choices=[
                    ("created", "Created"),
                    ("running", "Running"),
                    ("ended", "End"),
                ],
                default="created",
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="scrum",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "running")),
                fields=("team",),
                name="one_active_scrum_per_team",
            ),
        ),
    ]
