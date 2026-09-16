import secrets

from common.permissions import StrictDjangoModelPermissions, require_perm
from common.viewsets import OrganizationScopedModelViewSet
from platform_admin.service_auth import IsChannelGatewayService, ServiceTokenAuthentication
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .defaults import asegurar_canales
from .embedded_signup import IntercambioFallido, intercambiar_code_por_token
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
        # las actions `verificar`/`regenerar_webhook_secret` el permiso
        # correcto es `change_canal`, y ya se pide a mano en el propio
        # método — acá sólo hace falta estar autenticado para no chocar con
        # esa regla que no aplica.
        if self.action in ("verificar", "regenerar_webhook_secret", "whatsapp_exchange"):
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

    @action(detail=True, methods=["post"], url_path="regenerar-webhook-secret")
    def regenerar_webhook_secret(self, request, pk=None):
        """Rota el secreto de webhook de este canal (mismo criterio que
        `platform_admin.ServiceTokenViewSet.generar`) — invalida el valor
        anterior, así que hay que volver a pegarlo en la configuración del
        webhook de Meta después de esto. No aplica a Webchat."""
        require_perm(request, "channels.change_canal")
        canal = self.get_object()
        if canal.tipo not in Canal.TIPOS_CON_WEBHOOK_META:
            raise ValidationError("Este canal no usa webhook.")
        canal.webhook_secret = secrets.token_urlsafe(24)
        canal.save(update_fields=["webhook_secret"])
        return Response(self.get_serializer(canal).data)

    @action(detail=True, methods=["post"], url_path="whatsapp-exchange")
    def whatsapp_exchange(self, request, pk=None):
        """Embedded Signup de WhatsApp: el SDK de Facebook en el navegador
        termina el popup de alta y le da al frontend un `code` de un solo
        uso (para cambiar acá por el `access_token` real) más `phone_
        number_id`/`waba_id` (esos ya vienen resueltos del propio callback
        del SDK, no hace falta pedírselos a Meta de nuevo)."""
        require_perm(request, "channels.change_canal")
        canal = self.get_object()
        if canal.tipo != Canal.Tipo.WHATSAPP:
            raise ValidationError("El Embedded Signup es sólo para WhatsApp.")
        code = request.data.get("code")
        if not code:
            raise ValidationError("Falta el `code` del Embedded Signup.")

        try:
            access_token = intercambiar_code_por_token(code)
        except IntercambioFallido as exc:
            raise ValidationError(exc.detalle)

        canal.api_key = access_token
        canal.telefono_id = request.data.get("phone_number_id", canal.telefono_id)
        canal.waba_id = request.data.get("waba_id", canal.waba_id)
        canal.save(update_fields=["api_key", "telefono_id", "waba_id"])
        return Response(self.get_serializer(canal).data)


class InternalCanalConfigView(APIView):
    """Único lugar donde `api_key`/`webhook_secret` salen de Core en texto
    plano — sólo lo puede llamar Channel Gateway, autenticado con su
    `ServiceToken` interno (`platform_admin.service_auth`), nunca con el JWT
    de un usuario humano. Busca por `uuid` (no por `id` autoincremental)
    porque ese uuid es lo único que Meta manda de vuelta en la URL cuando
    llega un webhook (`webhook_url` en `CanalSerializer`) — es la única
    pista que tiene Channel Gateway para saber a qué organización/canal
    corresponde una request entrante, o con qué api_key mandar un mensaje
    saliente."""

    authentication_classes = [ServiceTokenAuthentication]
    permission_classes = [IsChannelGatewayService]

    def get(self, request, canal_uuid):
        canal = get_object_or_404(Canal, uuid=canal_uuid)
        return Response(_serializar_config(canal))


class InternalCanalPorOrganizacionView(APIView):
    """Mismos datos que `InternalCanalConfigView`, pero buscando por
    `(organization_id, tipo)` en vez de por `uuid` — hace falta porque Meta
    sólo deja configurar UNA Callback URL por app (no una por tipo de
    canal): Messenger/Instagram/WhatsApp de una misma organización entregan
    sus webhooks a la MISMA URL (la del canal que el Admin haya usado para
    configurar la suscripción en el dashboard de Meta), distinguibles sólo
    por el campo `object` del payload ("page"/"instagram"/
    "whatsapp_business_account"), nunca por la URL. Cuando el `object` del
    payload no coincide con el tipo del canal de la URL, Channel Gateway
    usa esto para encontrar el canal "hermano" correcto de la misma
    organización — ver `app/webhooks.py` del lado de Channel Gateway."""

    authentication_classes = [ServiceTokenAuthentication]
    permission_classes = [IsChannelGatewayService]

    def get(self, request, organization_id, tipo):
        canal = get_object_or_404(Canal, organization_id=organization_id, tipo=tipo.upper())
        return Response(_serializar_config(canal))


def _serializar_config(canal: Canal) -> dict:
    return {
        "organization_id": canal.organization_id,
        "tipo": canal.tipo,
        "api_key": canal.api_key,
        "telefono_id": canal.telefono_id,
        "waba_id": canal.waba_id,
        "webhook_secret": canal.webhook_secret,
        "activo": canal.activo,
    }
