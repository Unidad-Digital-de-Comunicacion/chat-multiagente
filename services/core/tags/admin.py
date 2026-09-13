from django.contrib import admin

from .models import Etiqueta


@admin.register(Etiqueta)
class EtiquetaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "organization", "team", "color", "es_sistema", "orden"]
    list_filter = ["organization", "es_sistema"]
    search_fields = ["nombre", "codigo"]
