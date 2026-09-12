from django.contrib import admin

from .models import Team


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "is_active", "created_at"]
    list_filter = ["organization", "is_active"]
    search_fields = ["name"]
    filter_horizontal = ["members"]
