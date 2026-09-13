from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["email"]
    list_display = ["email", "organization", "grupos", "is_active", "is_staff"]
    list_filter = ["organization", "groups", "is_active", "is_staff"]
    search_fields = ["email", "first_name", "last_name"]
    filter_horizontal = ["groups", "user_permissions"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("first_name", "last_name")}),
        ("Organización", {"fields": ("organization",)}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "organization", "groups", "password1", "password2"),
        }),
    )

    @admin.display(description="Grupos")
    def grupos(self, obj):
        return ", ".join(obj.groups.values_list("name", flat=True)) or "—"
