from django.contrib import admin

from .models import ActivityLog
from .models import BulkEmail  # noqa: E402


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "team", "actor_name", "action", "todo_title", "pm_notified_at")
    list_filter = ("action", "team")
    search_fields = ("actor_name", "todo_title")
    date_hierarchy = "created_at"
@admin.register(BulkEmail)
class BulkEmailAdmin(admin.ModelAdmin):
    list_display = ("created_at", "team", "sender_name", "subject", "recipient_count", "sent_count", "failed_count", "sent_at")
    list_filter = ("team",)
    search_fields = ("subject", "sender_name")