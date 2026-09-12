"""Permisos DRF compartidos por rol.

Roles disponibles (ver users.models.User.Role): admin, difusion, operador,
data_manager. Un superusuario de plataforma (sin organización) pasa siempre,
para poder operar soporte/administración cross-tenant desde /admin/.
"""
from rest_framework.permissions import BasePermission


class HasRole(BasePermission):
    allowed_roles: tuple = ()

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser:
            return True
        return user.role in self.allowed_roles

    @classmethod
    def for_roles(cls, *roles):
        return type("HasRoleDynamic", (cls,), {"allowed_roles": roles})


class IsOrgAdmin(HasRole):
    """Sólo el rol Admin gestiona usuarios, equipos, horarios y menú de su
    organización (ver Fase 1 en docs/CONTEXTO_PROYECTO.md)."""

    allowed_roles = ("admin",)


class IsOrgAdminOrReadOnly(IsOrgAdmin):
    SAFE_METHODS = ("GET", "HEAD", "OPTIONS")

    def has_permission(self, request, view):
        if request.method in self.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return super().has_permission(request, view)
