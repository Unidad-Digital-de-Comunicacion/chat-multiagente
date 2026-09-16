from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from common.permissions import StrictDjangoModelPermissions
from common.viewsets import OrganizationScopedModelViewSet

from .defaults import asegurar_etiquetas_equipo, asegurar_etiquetas_sistema
from .models import Etiqueta
from .serializers import EtiquetaSerializer


class EtiquetaViewSet(OrganizationScopedModelViewSet):
    """Catálogo de etiquetas de conversación: `tags.view_etiqueta` (admins +
    operadores de sólo lectura) para leer, `add_`/`change_`/`delete_etiqueta`
    (sólo administradores) para escribir — ver `users.group_permissions`.

    Dos orígenes autogenerados por organización la primera vez que se lista
    el catálogo (no se pueden borrar ni renombrar a mano, sólo recolorear):
    las 7 de sistema (pendiente/asignada/tomada/en_proceso/en_pausa/
    rechazado/resuelto) y una por cada `Team` ("cada equipo es una
    etiqueta" — se renombra sola si renombrás el equipo, se borra sola si
    borrás el equipo). Todo lo demás que arma un Admin a mano es una
    etiqueta general. Filtrable por `?team=<id>`.

    Esta app cubre únicamente la configuración del catálogo. Aplicar
    etiquetas a una conversación, las observaciones obligatorias al
    resolver/pausar y las notas internas entre operadores están en
    `conversations.views.ConversacionViewSet` (`etiquetas`/`observaciones`/
    `notas_internas`)."""

    queryset = Etiqueta.objects.all()
    serializer_class = EtiquetaSerializer
    permission_classes = [IsAuthenticated, StrictDjangoModelPermissions]

    def get_queryset(self):
        org_id = self.request.user.organization_id
        if org_id:
            asegurar_etiquetas_sistema(org_id)
            asegurar_etiquetas_equipo(org_id)
        qs = super().get_queryset()
        team_id = self.request.query_params.get("team")
        if team_id is not None:
            qs = qs.filter(team_id=team_id or None)
        return qs

    def perform_destroy(self, instance):
        if instance.es_sistema:
            raise ValidationError("Las etiquetas del sistema no se pueden eliminar, sólo recolorear.")
        if instance.team_id:
            raise ValidationError("La etiqueta de un equipo no se elimina a mano — se borra sola si borrás el equipo.")
        instance.delete()
