from common.permissions import StrictDjangoModelPermissions, require_perm
from common.viewsets import OrganizationScopedModelViewSet
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .defaults import asegurar_canales
from .health import verificar_conexion
from .models import Canal
from .serializers import CanalSerializer


class CanalViewSet(OrganizationScopedModelViewSet):
    """Configuración de canales de mensajería: `channels.view_canal` para
    leer, `channels.change_canal` para escribir (sólo administradores, ver
    `users.group_permissions`). Los 4 canales (WhatsApp/Messenger/Instagram/
    Webchat) se autogeneran por organización al listar. No hay permiso
    `channels.add_canal`/`delete_canal` en ningún grupo a propósito — nadie
    puede crear ni borrar canales por API, sólo editar `api_key`/`activo` de
    los 4 que ya existen (`StrictDjangoModelPermissions` lo bloquea con 403
    antes de llegar a `create`/`destroy`).

    Esta app cubre únicamente la configuración. La conexión real con cada
    canal (Embedded Signup, webhooks, envío de mensajes) es Channel Gateway,
    Fase 3 — todavía no implementada; la acción `verificar` de acá abajo es
    un adelanto acotado: un chequeo real de salud contra el servidor remoto
    (ver `channels.health`), no una integración completa."""

    queryset = Canal.objects.all()
    serializer_class = CanalSerializer
    permission_classes = [IsAuthenticated, StrictDjangoModelPermissions]

    def get_permissions(self):
        # `StrictDjangoModelPermissions` mapea POST -> `channels.add_canal`,
        # que ningún grupo tiene a propósito (los 4 canales son fijos). Para
        # la action `verificar` el permiso correcto es `change_canal`, y ya
        # se pide a mano en el propio método — acá sólo hace falta estar
        # autenticado para no chocar con esa regla que no aplica.
        if self.action == "verificar":
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        org_id = self.request.user.organization_id
        if org_id:
            asegurar_canales(org_id)
        return super().get_queryset()

    @action(detail=True, methods=["post"])
    def verificar(self, request, pk=None):
        """Chequeo real de salud del canal contra su servidor remoto (no un
        simulacro) — no mapea 1 a 1 a un CRUD, así que el permiso se pide a
        mano en vez de con `StrictDjangoModelPermissions`."""
        require_perm(request, "channels.change_canal")
        canal = self.get_object()
        verificar_conexion(canal)
        return Response(self.get_serializer(canal).data)
