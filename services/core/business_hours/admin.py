from django.contrib import admin

from .models import DiaExcepcional, HorarioAtencion


@admin.register(HorarioAtencion)
class HorarioAtencionAdmin(admin.ModelAdmin):
    list_display = ["organization", "dia_semana", "hora_inicio", "hora_fin", "activo"]
    list_filter = ["organization", "dia_semana", "activo"]


@admin.register(DiaExcepcional)
class DiaExcepcionalAdmin(admin.ModelAdmin):
    list_display = ["fecha", "organization", "tipo", "descripcion", "sincronizado"]
    list_filter = ["tipo", "sincronizado"]
    search_fields = ["descripcion"]
