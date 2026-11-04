from django.contrib import admin
from django.db.models import Count

from .models import Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "todo_count", "created_at")
    search_fields = ("name",)
    ordering = ("name",)
    readonly_fields = ("created_at",)

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_todo_count=Count("todos"))

    @admin.display(description="Todos using it", ordering="_todo_count")
    def todo_count(self, obj):
        # Deleting a category does NOT delete these todos; it only clears their category.
        return obj._todo_count