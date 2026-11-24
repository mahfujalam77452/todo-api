import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("scrums", "0001_initial"),
        ("todos", "0005_assignment_fields"),
    ]
    operations = [
        migrations.AddField(
            model_name="todo",
            name="scrum",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="todos",
                to="scrums.scrum",
            ),
        ),
        migrations.AddField(
            model_name="todo",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="todo",
            index=models.Index(
                fields=["scrum", "status", "-created_at", "-id"],
                name="todo_scrum_status_idx",
            ),
        ),
    ]
