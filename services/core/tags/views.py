from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from common.permissions import StrictDjangoModelPermissions
from common.viewsets import OrganizationScopedModelViewSet

from .defaults import asegurar_etiquetas_sistema
from .models import Etiqueta
from .serializers import EtiquetaSerializer


class EtiquetaViewSet(OrganizationScopedModelViewSet):
    """Catálogo de etiquetas de conversación: `tags.view_etiqueta` (admins +
    operadores de sólo lectura) para leer, `add_`/`change_`/`delete_etiqueta`
    (sólo administradores) para escribir — ver `users.group_permissions`.

    Las 7 etiquetas de sistema (pendiente/asignada/tomada/en_proceso/
    en_pausa/rechazado/resuelto) se autogeneran por organización la primera
    vez que se lista el catálogo; no se pueden borrar ni renombrar, sólo
    recolorear. Filtrable por `?team=<id>` para ver sólo las de un equipo.

    Esta app cubre únicamente la configuración del catálogo. Aplicar
    etiquetas a una conversación, las observaciones obligatorias al
    resolver/pausar y el chat interno entre operadores quedan documentados
    para Fase 4/5 en la sección 11 de docs/CONTEXTO_PROYECTO.md."""

    queryset = Etiqueta.objects.all()
    serializer_class = EtiquetaSerializer
    permission_classes = [IsAuthenticated, StrictDjangoModelPermissions]

    def get_queryset(self):
        org_id = self.request.user.organization_id
        if org_id:
            asegurar_etiquetas_sistema(org_id)
        qs = super().get_queryset()
        team_id = self.request.query_params.get("team")
        if team_id is not None:
            qs = qs.filter(team_id=team_id or None)
        return qs

    def perform_destroy(self, instance):
        if instance.es_sistema:
            raise ValidationError("Las etiquetas del sistema no se pueden eliminar, sólo recolorear.")
        instance.delete()
