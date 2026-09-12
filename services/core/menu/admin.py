from django.contrib import admin

from .models import MenuOpcion


@admin.register(MenuOpcion)
class MenuOpcionAdmin(admin.ModelAdmin):
    list_display = ["texto", "organization", "tipo", "parent", "team", "orden", "activo"]
    list_filter = ["organization", "tipo", "activo"]
    search_fields = ["texto", "slug"]
