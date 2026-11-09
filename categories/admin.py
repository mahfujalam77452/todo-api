from django.contrib import admin

from .models import Category


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admins manage the list of categories and nothing else: they have no
    relationship with todos (no todo is shown, listed or counted here).

    Deleting a category keeps every todo; the todos just lose that category.
    """

    list_display = ("name", "created_at")
    search_fields = ("name",)
    ordering = ("name",)
    readonly_fields = ("created_at",)