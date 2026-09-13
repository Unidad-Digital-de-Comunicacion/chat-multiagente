from django.contrib import admin

from .models import Canal


@admin.register(Canal)
class CanalAdmin(admin.ModelAdmin):
    list_display = ["tipo", "organization", "activo", "tiene_api_key", "updated_at"]
    list_filter = ["tipo", "activo", "organization"]

    @admin.display(boolean=True, description="API key cargada")
    def tiene_api_key(self, obj):
        return bool(obj.api_key)
