from django.db import models


class DashboardSetting(models.Model):
    overloaded_user_threshold = models.PositiveIntegerField(default=5)
    overdue_alert_threshold = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def current(cls):
        setting, _ = cls.objects.get_or_create(pk=1)
        return setting


class OverdueAlert(models.Model):
    scope_key = models.CharField(max_length=100, unique=True)
    overdue_count = models.PositiveIntegerField(default=0)
    threshold = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
