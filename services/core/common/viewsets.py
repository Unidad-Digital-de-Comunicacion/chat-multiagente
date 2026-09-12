"""Base de ViewSets que impone el aislamiento multi-tenant (sección 9 de
docs/CONTEXTO_PROYECTO.md): toda query se filtra por la organización del
usuario autenticado y toda creación fija esa misma organización, sin importar
lo que venga en el body de la request."""
from rest_framework import viewsets


class OrganizationScopedModelViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser and not user.organization_id:
            return qs
        return qs.filter(organization_id=user.organization_id)

    def perform_create(self, serializer):
        serializer.save(organization_id=self.request.user.organization_id)
