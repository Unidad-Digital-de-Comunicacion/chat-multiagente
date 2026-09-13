"""Base de ViewSets que impone el aislamiento multi-tenant (sección 9 de
docs/CONTEXTO_PROYECTO.md): toda query se filtra por la organización del
usuario autenticado y toda creación fija esa misma organización, sin importar
lo que venga en el body de la request.

Una cuenta de plataforma (sin `organization` — el superusuario real de
`common.permissions.IsPlatformSuperuser`, o cualquier otra cuenta sin
organización) NO tiene un equipo/menú/mensajes/etiquetas/horario/canales
propios que gestionar acá: a propósito ni siquiera `is_superuser=True` real
de Django hace una excepción (antes sí la hacía — se sacó porque el
superusuario de plataforma gestiona organizaciones/usuarios/tokens desde la
sección "Plataforma", nunca la configuración interna de una organización en
particular; ver la sección "Sección Plataforma del Admin Panel" de
docs/CONTEXTO_PROYECTO.md)."""
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied

_SIN_ORGANIZACION = "Este recurso es de una organización — no aplica a una cuenta de plataforma."


class OrganizationScopedModelViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        qs = super().get_queryset()
        organization_id = self.request.user.organization_id
        if not organization_id:
            raise PermissionDenied(_SIN_ORGANIZACION)
        return qs.filter(organization_id=organization_id)

    def perform_create(self, serializer):
        organization_id = self.request.user.organization_id
        if not organization_id:
            raise PermissionDenied(_SIN_ORGANIZACION)
        serializer.save(organization_id=organization_id)
