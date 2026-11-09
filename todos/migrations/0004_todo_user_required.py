import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def delete_unowned_todos(apps, schema_editor):
    """Before accounts existed (phases 1-3) a todo had no owner. With
    ownership required, such a row could never be shown to anybody, and
    giving it to some user would hand them data that is not theirs. Only
    development databases can contain them; they are removed."""
    Todo = apps.get_model("todos", "Todo")
    Todo.objects.filter(user__isnull=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("todos", "0003_todo_indexes"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(delete_unowned_todos, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="todo",
            name="user",
            field=models.ForeignKey(
                db_index=False,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="todos",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]