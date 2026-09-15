"""`MensajeEntranteView` es el endpoint interno que documenta la sección 4.1
de docs/CONTEXTO_PROYECTO.md (`POST /api/core/bot/mensaje-entrante/`) — sólo
lo llama Channel Gateway (mismo `ServiceTokenAuthentication` que `channels.
views.InternalCanalConfigView`), nunca un usuario. `ConversacionViewSet` es
la API que usa el frontend nuevo `operators-desk-web`: bandeja + tomar +
responder + cerrar. Ver el docstring de `models.py` para qué le falta
todavía a esto (selección nativa por canal, asignación real de Conversation
Engine)."""
from django.utils import timezone

from bot_settings.models import BotMessages
from common.permissions import StrictDjangoModelPermissions, require_organization, require_perm
from organizations.models import Organization
from platform_admin.service_auth import IsChannelGatewayService, ServiceTokenAuthentication
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .channel_gateway_client import enviar_mensaje_saliente
from .menu_engine import procesar_seleccion, render_menu
from .models import Contact, Conversacion, ConversacionLog
from .serializers import ConversacionLogSerializer, ConversacionSerializer


class MensajeEntranteView(APIView):
    """Channel Gateway llama acá por cada mensaje de texto normalizado que
    recibe. Devuelve `{"acciones": [{"tipo": "enviar_texto", "texto": "..."}]}`.

    En el primer contacto: mensaje de bienvenida y, si `BotMessages.
    menu_activo` y hay `MenuOpcion` configuradas, el menú principal (ver
    `menu_engine.render_menu`) — si no hay nada configurado, se pasa
    directo al modo "sin menú" (`Conversacion.menu_finalizado=True`, la
    conversación queda en la bandeja sin asignar).

    En mensajes siguientes: mientras la conversación siga sin tomar un
    operador Y `menu_finalizado` sea `False`, el texto se interpreta como
    la opción elegida (`menu_engine.procesar_seleccion`). Una vez que un
    operador toma la conversación, o el menú terminó (derivación/fin/
    "Terminar"), los mensajes sólo quedan logueados para que los vea el
    operador — no hay más respuesta automática."""

    authentication_classes = [ServiceTokenAuthentication]
    permission_classes = [IsChannelGatewayService]
    # `request.user` queda anónimo con `ServiceTokenAuthentication` (no hay
    # un usuario humano detrás) — sin esto, `AnonRateThrottle` (20/minuto)
    # aplicaría acá, muy por debajo de lo que un canal real puede recibir.
    # La protección real de este endpoint es `IsChannelGatewayService`, no
    # un límite de tasa.
    throttle_classes = []

    def post(self, request):
        organization_id = request.data.get("organization_id")
        canal = request.data.get("channel")
        contact_externo_id = request.data.get("contact_externo_id")
        texto = request.data.get("texto")
        if not all([organization_id, canal, contact_externo_id, texto]):
            raise ValidationError("Faltan campos: organization_id, channel, contact_externo_id, texto.")
        try:
            organization = Organization.objects.get(pk=organization_id)
        except Organization.DoesNotExist:
            raise NotFound("No existe esa organización.")

        contact, _ = Contact.objects.get_or_create(
            organization=organization, canal=canal, identificador_externo=contact_externo_id,
        )
        conversacion = Conversacion.objects.filter(
            contact=contact, estado=Conversacion.Estado.ABIERTA,
        ).order_by("-iniciada_at").first()

        acciones = []
        if conversacion is None:
            conversacion = Conversacion.objects.create(organization=organization, contact=contact, canal=canal)
            bot_messages = BotMessages.para_organizacion(organization)
            bienvenida = bot_messages.valor_o_default("mensaje_bienvenida")
            if bienvenida:
                acciones.append({"tipo": "enviar_texto", "texto": bienvenida})
            menu_inicial = render_menu(organization_id, None) if bot_messages.menu_activo else None
            if menu_inicial:
                acciones.append({"tipo": "enviar_texto", "texto": menu_inicial})
            else:
                conversacion.menu_finalizado = True
                conversacion.save(update_fields=["menu_finalizado"])
        elif not conversacion.menu_finalizado and conversacion.operador_id is None:
            acciones = procesar_seleccion(conversacion, texto)

        ConversacionLog.objects.create(
            conversacion=conversacion, remitente=ConversacionLog.Remitente.CONTACTO, texto=texto,
        )
        return Response({"acciones": acciones})


class ConversacionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Sin alta/baja/edición directa por API a propósito — las conversaciones
    las crea sólo `MensajeEntranteView`, y sólo cambian de estado a través de
    las actions de acá abajo (nunca un PATCH libre, que se saltearía el
    envío del mensaje de despedida al cerrar, por ejemplo)."""

    serializer_class = ConversacionSerializer
    permission_classes = [IsAuthenticated, StrictDjangoModelPermissions]

    def get_queryset(self):
        organization_id = require_organization(self.request)
        qs = Conversacion.objects.filter(organization_id=organization_id).select_related("contact", "operador", "team")
        bandeja = self.request.query_params.get("bandeja")
        if bandeja == "sin_asignar":
            qs = qs.filter(operador__isnull=True, estado=Conversacion.Estado.ABIERTA)
        elif bandeja == "mias":
            qs = qs.filter(operador=self.request.user)
        return qs

    def get_permissions(self):
        # Ninguna de estas 4 actions mapea 1 a 1 a un CRUD (todas son POST/GET
        # que no son ni add/change/delete "genéricos" de `StrictDjango
        # ModelPermissions") — mismo criterio que `channels.CanalViewSet.
        # verificar`: el permiso real se pide a mano en cada método.
        if self.action in ("tomar", "mensajes", "responder", "cerrar"):
            return [IsAuthenticated()]
        return super().get_permissions()

    @action(detail=True, methods=["post"])
    def tomar(self, request, pk=None):
        require_perm(request, "conversations.change_conversacion")
        conversacion = self.get_object()
        if conversacion.operador_id is not None:
            raise ValidationError("Esta conversación ya está tomada.")
        conversacion.operador = request.user
        conversacion.save(update_fields=["operador", "updated_at"])
        return Response(self.get_serializer(conversacion).data)

    @action(detail=True, methods=["get"])
    def mensajes(self, request, pk=None):
        require_perm(request, "conversations.view_conversacion")
        conversacion = self.get_object()
        mensajes = conversacion.mensajes.all()
        return Response(ConversacionLogSerializer(mensajes, many=True).data)

    @action(detail=True, methods=["post"])
    def responder(self, request, pk=None):
        require_perm(request, "conversations.change_conversacion")
        conversacion = self.get_object()
        if conversacion.operador_id != request.user.id:
            raise PermissionDenied("Esta conversación no está tomada por vos.")
        if conversacion.estado != Conversacion.Estado.ABIERTA:
            raise ValidationError("Esta conversación ya está cerrada.")
        texto = (request.data.get("texto") or "").strip()
        if not texto:
            raise ValidationError("Falta el texto.")

        entregado = enviar_mensaje_saliente(conversacion, texto)
        ConversacionLog.objects.create(conversacion=conversacion, remitente=ConversacionLog.Remitente.OPERADOR, texto=texto)
        conversacion.save(update_fields=["updated_at"])
        return Response({"entregado": entregado})

    @action(detail=True, methods=["post"])
    def cerrar(self, request, pk=None):
        require_perm(request, "conversations.change_conversacion")
        conversacion = self.get_object()
        if conversacion.operador_id != request.user.id:
            raise PermissionDenied("Esta conversación no está tomada por vos.")
        if conversacion.estado != Conversacion.Estado.ABIERTA:
            raise ValidationError("Esta conversación ya está cerrada.")

        conversacion.estado = Conversacion.Estado.CERRADA
        conversacion.cerrada_at = timezone.now()
        conversacion.save(update_fields=["estado", "cerrada_at", "updated_at"])

        despedida = BotMessages.para_organizacion(conversacion.contact.organization).valor_o_default("mensaje_despedida")
        if despedida:
            enviar_mensaje_saliente(conversacion, despedida)
            ConversacionLog.objects.create(conversacion=conversacion, remitente=ConversacionLog.Remitente.SISTEMA, texto=despedida)

        return Response(self.get_serializer(conversacion).data)
