from .models import Notification


def _todo_link(todo):
    return f"/todos/{todo.pk}"


def notify_assigned(todo, recipient):
    return Notification.objects.create(
        recipient=recipient,
        type=Notification.Type.ASSIGNED,
        message=f"You were assigned todo: {todo.title}",
        todo=todo,
        link=_todo_link(todo),
    )


def notify_accepted(todo, recipient):
    return Notification.objects.create(
        recipient=recipient,
        type=Notification.Type.ACCEPTED,
        message=f"{todo.assignee.name} accepted todo: {todo.title}",
        todo=todo,
        link=_todo_link(todo),
    )


def notify_rejected(todo, recipient, reason=None):
    message = f"{todo.assignee.name} rejected todo: {todo.title}"
    if reason:
        message = f"{message} ({reason})"
    return Notification.objects.create(
        recipient=recipient,
        type=Notification.Type.REJECTED,
        message=message,
        todo=todo,
        link=_todo_link(todo),
    )
