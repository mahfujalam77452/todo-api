from django.contrib import admin

from .models import Membership, Team


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "member_count")
    search_fields = ("name",)
    inlines = [MembershipInline]

    @admin.display(description="Members")
    def member_count(self, obj):
        return obj.memberships.count()


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "team", "joined_at")
    list_filter = ("team",)
    search_fields = ("user__email", "user__name", "team__name")
    autocomplete_fields = ("user", "team")
