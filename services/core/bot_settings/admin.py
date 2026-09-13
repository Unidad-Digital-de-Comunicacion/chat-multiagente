from django.contrib import admin

from .models import BotMessages


@admin.register(BotMessages)
class BotMessagesAdmin(admin.ModelAdmin):
    list_display = ["organization", "updated_at"]
    search_fields = ["organization__name"]
