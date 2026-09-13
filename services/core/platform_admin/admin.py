from django.contrib import admin

from .models import ServiceToken


@admin.register(ServiceToken)
class ServiceTokenAdmin(admin.ModelAdmin):
    list_display = ["servicio", "tiene_token", "activo", "generado_at", "updated_at"]

    @admin.display(boolean=True, description="Token cargado")
    def tiene_token(self, obj):
        return bool(obj.token)
