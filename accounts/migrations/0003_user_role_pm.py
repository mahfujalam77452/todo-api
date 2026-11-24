from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_role"),
    ]

    operations = [
        migrations.RemoveConstraint(model_name="user", name="user_role_valid"),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[("member", "Member"), ("pm", "Project Manager"), ("admin", "Admin")],
                default="member",
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=Q(role__in=["member", "pm", "admin"]),
                name="user_role_valid",
            ),
        ),
    ]