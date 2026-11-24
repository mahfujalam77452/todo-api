import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [("teams", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="Scrum",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("status", models.CharField(choices=[("active", "Active"), ("completed", "Completed")], default="completed", max_length=20)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("ended_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("team", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="scrums", to="teams.team")),
            ],
            options={"ordering": ["-started_at", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="scrum",
            constraint=models.UniqueConstraint(condition=models.Q(("status", "active")), fields=("team",), name="one_active_scrum_per_team"),
        ),
        migrations.AddIndex(
            model_name="scrum",
            index=models.Index(fields=["team", "status", "-started_at"], name="scrums_scru_team_id_140c83_idx"),
        ),
    ]
