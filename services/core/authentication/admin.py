from django.contrib import admin

from .models import LoginLockout


@admin.register(LoginLockout)
class LoginLockoutAdmin(admin.ModelAdmin):
    list_display = ["ip_address", "failed_attempts", "blocked_until", "is_blocked", "last_attempt_at"]
    list_filter = ["blocked_until"]
    search_fields = ["ip_address"]
    readonly_fields = ["last_attempt_at"]
    actions = ["desbloquear"]

    @admin.display(boolean=True, description="Bloqueada")
    def is_blocked(self, obj):
        return obj.is_blocked

    @admin.action(description="Desbloquear las IPs seleccionadas")
    def desbloquear(self, request, queryset):
        actualizadas = queryset.update(failed_attempts=0, blocked_until=None)
        self.message_user(request, f"{actualizadas} IP(s) desbloqueada(s).")
