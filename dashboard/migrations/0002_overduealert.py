from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("dashboard", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="OverdueAlert",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("scope_key", models.CharField(max_length=100, unique=True)),
                ("overdue_count", models.PositiveIntegerField(default=0)),
                ("threshold", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"ordering": ["-created_at", "-id"]},
        ),
    ]
