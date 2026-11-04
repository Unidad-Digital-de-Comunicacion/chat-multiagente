from django.contrib import admin

from .models import ChequeoSalud, CursorLog, Incidente


@admin.register(Incidente)
class IncidenteAdmin(admin.ModelAdmin):
    list_display = ("titulo", "tipo", "estado", "servicio", "ocurrencias", "ultima_vez", "notificado_at")
    list_filter = ("estado", "tipo", "servicio")
    search_fields = ("titulo", "detalle")
    readonly_fields = ("huella",)


@admin.register(ChequeoSalud)
class ChequeoSaludAdmin(admin.ModelAdmin):
    list_display = ("nombre", "url", "ok", "fallos_consecutivos", "ultimo_chequeo_at")


admin.site.register(CursorLog)
