from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "team", "actor_name", "action", "todo_title", "pm_notified_at")
    list_filter = ("action", "team")
    search_fields = ("actor_name", "todo_title")
    date_hierarchy = "created_at"