"""`MensajeEntranteView` es el endpoint interno que documenta la sección 4.1
de docs/CONTEXTO_PROYECTO.md (`POST /api/core/bot/mensaje-entrante/`) — sólo
lo llama Channel Gateway (mismo `ServiceTokenAuthentication` que `channels.
views.InternalCanalConfigView`), nunca un usuario. `ConversacionViewSet` es
la API que usan tanto `operators-desk-web` como la app Android (mismo
contrato para los dos, sección 3.2): bandeja + tomar + responder + cerrar +
derivar + etiquetas + observaciones + notas internas. `historial` es
aparte — para `administradores` en el Admin Panel, no para operadores (ver
su docstring). Cada action que
cambia algo relevante para la bandeja avisa además a Conversation Engine
(`conversation_engine_client.notificar_evento`, mejor esfuerzo — ver su
docstring) para que lo reenvíe por WebSocket a quien tenga la app abierta;
si eso falla o no está configurado, el cliente se entera igual por
polling. Ver el docstring de `models.py` para qué le falta todavía a esto
(selección nativa por canal)."""
from datetime import timedelta

from django.db.models import Max, OuterRef, Prefetch, Q, Subquery
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
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
from tags.models import Etiqueta
from teams.models import Team

from .channel_gateway_client import enviar_con_reintentos
from .cierre import cerrar_conversacion
from .conversation_engine_client import notificar_evento
from .etiqueta_sistema import sincronizar_etiqueta_estado
from .menu_engine import accion_menu, procesar_seleccion, render_menu
from .models import (
    Contact, Conversacion, ConversacionEtiqueta, ConversacionLog, ConversacionNotaInterna, ConversacionObservacion,
)
from .serializers import (
    AplicarEtiquetaInputSerializer, ConversacionEtiquetaSerializer, ConversacionHistorialSerializer,
    ConversacionLogSerializer, ConversacionNotaInternaSerializer, ConversacionObservacionSerializer,
    ConversacionSerializer, DerivarInputSerializer, HistorialFiltrosSerializer, NotaInternaInputSerializer,
    ObservacionInputSerializer,
)

# Las 3 únicas etiquetas de sistema donde una observación vacía no alcanza
# (pedido explícito, sección 11/Fase 5 de docs/CONTEXTO_PROYECTO.md): hay
# que poder explicar POR QUÉ se resolvió positiva/negativamente o se
# pausó, para que otro operador que retome la conversación tenga contexto.
CODIGOS_QUE_EXIGEN_OBSERVACION = {"resuelto", "rechazado", "en_pausa"}


# `prefetch_related` compartido por `ConversacionViewSet.historial` y
# `platform_admin.views.HistorialConversacionesPlatformView` — las dos
# devuelven `ConversacionHistorialSerializer`, que ahora incluye etiquetas/
# observaciones (ver su docstring); sin esto cada fila dispararía 2 queries
# extra (N+1) por conversación listada.
PREFETCH_HISTORIAL = (
    Prefetch("etiquetas_aplicadas", queryset=ConversacionEtiqueta.objects.select_related("etiqueta", "aplicada_por")),
    Prefetch("observaciones", queryset=ConversacionObservacion.objects.select_related("operador")),
)


def anotar_ultima_actividad(queryset):
    """`ultima_actividad`: último `ConversacionLog` (de cualquier
    remitente) de la conversación, o `iniciada_at` si todavía no tiene
    ninguno — mismo criterio y mismo fallback que usa `management.
    commands.cerrar_conversaciones_inactivas` para decidir qué está
    inactiva, así las dos coinciden en qué cuenta como "sin actividad".
    También anota `minutos_inactividad_cierre` (subquery a `BotMessages`
    de la organización de cada fila, NULL si esa organización todavía no
    tiene una — `get_or_create` en un listado sería un efecto secundario
    no deseado) — entre las dos alcanza para que el serializer calcule
    `vencida_por_inactividad` sin queries extra por fila."""
    minutos_subquery = BotMessages.objects.filter(organization_id=OuterRef("organization_id")).values(
        "minutos_inactividad_cierre",
    )[:1]
    return queryset.annotate(
        ultima_actividad=Coalesce(Max("mensajes__creado_at"), "iniciada_at"),
        minutos_inactividad_cierre=Subquery(minutos_subquery),
    )


def aplicar_filtros_historial(queryset, request):
    """Filtros comunes a `ConversacionViewSet.historial` (una organización)
    y `platform_admin.views.HistorialConversacionesPlatformView` (todas) —
    mismo shape de query params en los dos, factorizado acá para no
    duplicar la lógica. `entrada.validated_data` ya viene limpio
    (`HistorialFiltrosSerializer` valida tipos/formato, un `canal`/`desde`
    con basura da 400 en vez de un 500 al pegarle directo al ORM)."""
    entrada = HistorialFiltrosSerializer(data=request.query_params)
    entrada.is_valid(raise_exception=True)
    datos = entrada.validated_data

    if datos.get("canal"):
        queryset = queryset.filter(canal=datos["canal"])
    if datos.get("team") is not None:
        queryset = queryset.filter(team_id=datos["team"])
    if datos.get("derivada") is not None:
        queryset = queryset.filter(team__isnull=not datos["derivada"])
    if datos.get("desde"):
        queryset = queryset.filter(iniciada_at__date__gte=datos["desde"])
    if datos.get("hasta"):
        queryset = queryset.filter(iniciada_at__date__lte=datos["hasta"])
    if datos.get("q"):
        queryset = queryset.filter(
            Q(contact__identificador_externo__icontains=datos["q"]) | Q(contact__nombre__icontains=datos["q"]),
        )
    return queryset


def _registrar_salientes(conversacion: Conversacion, acciones: list[dict]) -> None:
    """Deja constancia real (no inferible después del hecho) de cada
    mensaje automático que el bot mandó — `enviar_texto` y `mostrar_menu`
    (acá el `texto` es el fallback con el listado numerado, el mismo
    contenido sustancial se haya mandado como texto plano o como widget
    nativo). Antes de esto, sólo quedaba loguado lo que escribía el
    contacto — nada de lo que el bot le contestaba, lo que hacía imposible
    reconstruir una conversación completa después del hecho."""
    for accion in acciones:
        texto = accion.get("texto")
        if texto:
            ConversacionLog.objects.create(
                conversacion=conversacion, remitente=ConversacionLog.Remitente.SISTEMA, texto=texto,
            )


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
            sincronizar_etiqueta_estado(conversacion)
            bot_messages = BotMessages.para_organizacion(organization)
            bienvenida = bot_messages.valor_o_default("mensaje_bienvenida")
            if bienvenida:
                acciones.append({"tipo": "enviar_texto", "texto": bienvenida})
            menu_inicial = render_menu(organization_id, None) if bot_messages.menu_activo else None
            menu_accion = accion_menu(menu_inicial)
            if menu_accion:
                acciones.append(menu_accion)
            else:
                conversacion.menu_finalizado = True
                conversacion.save(update_fields=["menu_finalizado"])
        elif not conversacion.menu_finalizado and conversacion.operador_id is None:
            acciones = procesar_seleccion(conversacion, texto)

        ConversacionLog.objects.create(
            conversacion=conversacion, remitente=ConversacionLog.Remitente.CONTACTO, texto=texto,
        )
        _registrar_salientes(conversacion, acciones)
        # Cubre tanto "mensaje nuevo" como cualquier cambio de estado que
        # haya disparado el motor de menú en el camino (derivación a un
        # equipo, asignación por round-robin, cierre por "Terminar") — un
        # solo aviso al final, no hace falta instrumentar `menu_engine.py`.
        notificar_evento(
            tipo="mensaje_nuevo", organization_id=organization.id, conversacion_id=conversacion.id,
            team_id=conversacion.team_id, operador_id=conversacion.operador_id,
        )
        return Response({"acciones": acciones})


class ConversacionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Sin alta/baja/edición directa por API a propósito — las conversaciones
    las crea sólo `MensajeEntranteView`, y sólo cambian de estado a través de
    las actions de acá abajo (nunca un PATCH libre, que se saltearía el
    envío del mensaje de despedida al cerrar, por ejemplo)."""

    LOCK_MINUTOS = 2

    serializer_class = ConversacionSerializer
    permission_classes = [IsAuthenticated, StrictDjangoModelPermissions]

    def get_queryset(self):
        organization_id = require_organization(self.request)
        qs = Conversacion.objects.filter(organization_id=organization_id).select_related(
            "contact", "operador", "team",
        ).prefetch_related(
            Prefetch("etiquetas_aplicadas", queryset=ConversacionEtiqueta.objects.select_related("etiqueta")),
            # Orden propio (más nueva primero), distinto del `ordering` del
            # modelo (cronológico) — sólo para `ConversacionSerializer.
            # get_ultima_observacion`, que necesita la última. Un `.filter()`/
            # `.select_related()`/`.order_by()` posterior sobre este related
            # manager (como el que ya hace la action `observaciones`) ignora
            # este prefetch y dispara su propia query, así que esto no
            # cambia el orden cronológico que ya devuelve esa action.
            Prefetch("observaciones", queryset=ConversacionObservacion.objects.order_by("-creado_at")),
        )
        bandeja = self.request.query_params.get("bandeja")
        if bandeja == "sin_asignar":
            # "Sin asignar" de verdad, MÁS lo que quedó asignado (por
            # round-robin o a mano) pero cuyo `bloqueada_hasta` ya venció
            # sin que nadie respondiera — vuelve a estar disponible para
            # que cualquier operador lo reclame (ver `tomar`).
            ahora = timezone.now()
            qs = qs.filter(estado=Conversacion.Estado.ABIERTA).filter(
                Q(operador__isnull=True) | Q(bloqueada_hasta__lt=ahora),
            )
        elif bandeja == "mias":
            qs = qs.filter(operador=self.request.user, estado=Conversacion.Estado.ABIERTA)
        elif bandeja == "cerradas":
            qs = qs.filter(operador=self.request.user, estado=Conversacion.Estado.CERRADA)
        return qs

    def get_permissions(self):
        # Ninguna de estas actions mapea 1 a 1 a un CRUD (todas son POST/GET/
        # DELETE que no son ni add/change/delete "genéricos" de `StrictDjango
        # ModelPermissions`) — mismo criterio que `channels.CanalViewSet.
        # verificar`: el permiso real se pide a mano en cada método, siempre
        # `conversations.view_/change_conversacion` (nunca un permiso propio
        # de `ConversacionEtiqueta`/`ConversacionObservacion`/
        # `ConversacionNotaInterna` — son detalle de una conversación, no
        # recursos que se administren aparte).
        if self.action in (
            "tomar", "mensajes", "responder", "cerrar", "derivar",
            "etiquetas", "quitar_etiqueta", "observaciones", "notas_internas", "historial",
        ):
            return [IsAuthenticated()]
        return super().get_permissions()

    @action(detail=False, methods=["get"])
    def historial(self, request):
        """Historial resumido (inicio/derivación/fin/etiquetas/
        observaciones, `ConversacionHistorialSerializer`) de TODAS las
        conversaciones de la organización — abiertas y cerradas, a
        diferencia de `bandeja`. Gate propio (`ver_historial_conversacion`,
        ver `Conversacion.Meta.permissions`) en vez de `view_conversacion`
        — ese sigue siendo sólo de operadores, y desbloquea `mensajes`/
        `notas_internas`, que acá justamente NO corresponde exponer
        (pensado para `administradores`, que audita el flujo — quién
        derivó, quién tomó, qué etiquetas/observaciones dejó — sin leer el
        contenido real de los mensajes ni las notas operador-a-operador).
        El superusuario de
        plataforma ve todas las organizaciones a la vez por
        `platform_admin.views.HistorialConversacionesPlatformView`, no
        por acá — esto sigue scopeado a una sola organización. Filtros
        (opcionales, ver `HistorialFiltrosSerializer`): `?canal=`, `?team=`,
        `?derivada=true|false`, `?desde=`/`?hasta=` (YYYY-MM-DD, sobre
        `iniciada_at`), `?q=` (busca en teléfono/usuario del contacto).
        Ordenado por `ultima_actividad` descendente (la más reciente
        primero) — ver `anotar_ultima_actividad`."""
        require_perm(request, "conversations.ver_historial_conversacion")
        organization_id = require_organization(request)
        queryset = Conversacion.objects.filter(organization_id=organization_id).select_related(
            "contact", "operador", "team",
        ).prefetch_related(*PREFETCH_HISTORIAL)
        queryset = anotar_ultima_actividad(queryset)
        queryset = aplicar_filtros_historial(queryset, request).order_by("-ultima_actividad")
        page = self.paginate_queryset(queryset)
        serializer = ConversacionHistorialSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=["post"])
    def tomar(self, request, pk=None):
        """Reclama la conversación — sirve tanto para tomar una sin asignar
        como para reclamar una cuyo lock de `LOCK_MINUTOS` ya venció (ver
        `get_queryset`). Mientras el lock de OTRO operador siga vigente, no
        se puede tomar, aunque técnicamente ya no esté "sin asignar".
        Sin `tomar_sin_derivar`, no se puede tomar una que todavía esté
        "pendiente" (sin `team`) — hay que esperar a que el árbol de menú
        la derive sola, o derivarla a mano primero (pedido explícito)."""
        require_perm(request, "conversations.change_conversacion")
        conversacion = self.get_object()
        if conversacion.team_id is None and not request.user.has_perm("conversations.tomar_sin_derivar"):
            raise PermissionDenied("Esta conversación todavía no fue derivada a un equipo.")
        ahora = timezone.now()
        tomada_por_otro_vigente = (
            conversacion.operador_id is not None
            and conversacion.operador_id != request.user.id
            and conversacion.bloqueada_hasta is not None
            and conversacion.bloqueada_hasta > ahora
        )
        if tomada_por_otro_vigente:
            raise ValidationError("Esta conversación está tomada por otro operador.")
        conversacion.operador = request.user
        conversacion.bloqueada_hasta = ahora + timedelta(minutes=self.LOCK_MINUTOS)
        conversacion.save(update_fields=["operador", "bloqueada_hasta", "updated_at"])
        sincronizar_etiqueta_estado(conversacion, aplicada_por=request.user)
        notificar_evento(
            tipo="conversacion_actualizada", organization_id=conversacion.organization_id,
            conversacion_id=conversacion.id, team_id=conversacion.team_id, operador_id=conversacion.operador_id,
        )
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

        # Se loguea ANTES de intentar el envío (no después): con reintentos
        # de por medio (`enviar_con_reintentos` puede tardar unos segundos
        # si el primer intento falla) el operador tiene que ver su propio
        # mensaje en el hilo al toque, no recién cuando termina de
        # reintentar — si los 3 intentos fallan, el aviso "No se pudo
        # enviar este mensaje." queda logueado aparte, a continuación.
        ConversacionLog.objects.create(conversacion=conversacion, remitente=ConversacionLog.Remitente.OPERADOR, texto=texto)
        entregado = enviar_con_reintentos(conversacion, texto)
        # Renueva el lock — una conversación activamente atendida no
        # debería quedar disponible para que otro operador la reclame a
        # mitad de camino sólo porque pasaron 2 minutos desde que se tomó.
        conversacion.bloqueada_hasta = timezone.now() + timedelta(minutes=self.LOCK_MINUTOS)
        conversacion.save(update_fields=["updated_at", "bloqueada_hasta"])
        return Response({"entregado": entregado})

    @action(detail=True, methods=["post"])
    def cerrar(self, request, pk=None):
        """Pedido explícito: no se puede cerrar sin haber dejado constancia
        de por qué/cómo terminó (`observaciones`, §4.9 del contrato de
        API) — no confundir con la `observacion` puntual que ya exige
        aplicar una etiqueta de sistema tipo `resuelto`/`rechazado`/
        `en_pausa` (§4.8): esa es una de las formas válidas de cumplir
        esto, no hace falta cargar una segunda observación aparte."""
        require_perm(request, "conversations.change_conversacion")
        conversacion = self.get_object()
        if conversacion.operador_id != request.user.id:
            raise PermissionDenied("Esta conversación no está tomada por vos.")
        if conversacion.estado != Conversacion.Estado.ABIERTA:
            raise ValidationError("Esta conversación ya está cerrada.")
        if not conversacion.observaciones.exists():
            raise ValidationError({
                "observacion": ["Hace falta cargar al menos una observación antes de cerrar la conversación."],
            })

        despedida = BotMessages.para_organizacion(conversacion.contact.organization).valor_o_default("mensaje_despedida")
        cerrar_conversacion(conversacion, mensaje=despedida)
        return Response(self.get_serializer(conversacion).data)

    @action(detail=True, methods=["post"])
    def derivar(self, request, pk=None):
        """Deriva a mano una conversación ya en curso a otro equipo —
        distinto de la derivación automática del árbol de menú
        (`menu_engine.procesar_seleccion`, que sólo pasa mientras el
        contacto sigue en modo bot): acá el operador ya la venía atendiendo
        (o estaba sin asignar en la bandeja de otro equipo) y decide
        pasarla. Vuelve a quedar sin operador asignado (libre para que
        cualquiera del equipo destino la tome) — pedido explícito (sección
        11/Fase 5): requiere indicar el motivo en `observacion`."""
        require_perm(request, "conversations.change_conversacion")
        conversacion = self.get_object()
        if conversacion.estado != Conversacion.Estado.ABIERTA:
            raise ValidationError("Esta conversación ya está cerrada.")

        entrada = DerivarInputSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        team = get_object_or_404(Team, pk=entrada.validated_data["team"], organization_id=conversacion.organization_id)

        conversacion.team = team
        conversacion.operador = None
        conversacion.bloqueada_hasta = None
        conversacion.derivada_at = timezone.now()
        conversacion.save(update_fields=["team", "operador", "bloqueada_hasta", "derivada_at", "updated_at"])
        ConversacionObservacion.objects.create(
            conversacion=conversacion, operador=request.user, texto=entrada.validated_data["observacion"].strip(),
        )
        sincronizar_etiqueta_estado(conversacion, aplicada_por=request.user)
        notificar_evento(
            tipo="conversacion_actualizada", organization_id=conversacion.organization_id,
            conversacion_id=conversacion.id, team_id=conversacion.team_id, operador_id=conversacion.operador_id,
        )
        return Response(self.get_serializer(conversacion).data)

    @action(detail=True, methods=["get", "post"], url_path="etiquetas")
    def etiquetas(self, request, pk=None):
        """GET: etiquetas hoy aplicadas a esta conversación (de sistema, de
        equipo o generales — mismo catálogo de `tags.EtiquetaViewSet`). POST
        `{etiqueta, observacion?}`: aplica una — si es de sistema, saca
        cualquier otra etiqueta de sistema que ya estuviera (mutuamente
        excluyentes, sólo puede haber un estado activo a la vez) y exige
        `observacion` no vacía si el código es resuelto/rechazado/en_pausa
        (pedido explícito, sección 11/Fase 5)."""
        conversacion = self.get_object()
        if request.method == "GET":
            require_perm(request, "conversations.view_conversacion")
            aplicadas = conversacion.etiquetas_aplicadas.select_related("etiqueta", "aplicada_por")
            return Response(ConversacionEtiquetaSerializer(aplicadas, many=True).data)

        require_perm(request, "conversations.change_conversacion")
        entrada = AplicarEtiquetaInputSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        etiqueta = get_object_or_404(
            Etiqueta, pk=entrada.validated_data["etiqueta"], organization_id=conversacion.organization_id,
        )
        observacion_texto = entrada.validated_data["observacion"].strip()
        if etiqueta.codigo in CODIGOS_QUE_EXIGEN_OBSERVACION and not observacion_texto:
            raise ValidationError({
                "observacion": f"Hace falta cargar una observación para marcar la conversación como «{etiqueta.nombre}».",
            })

        if etiqueta.es_sistema:
            conversacion.etiquetas_aplicadas.filter(etiqueta__es_sistema=True).exclude(etiqueta=etiqueta).delete()
        ConversacionEtiqueta.objects.update_or_create(
            conversacion=conversacion, etiqueta=etiqueta, defaults={"aplicada_por": request.user},
        )
        if observacion_texto:
            ConversacionObservacion.objects.create(conversacion=conversacion, operador=request.user, texto=observacion_texto)

        notificar_evento(
            tipo="conversacion_actualizada", organization_id=conversacion.organization_id,
            conversacion_id=conversacion.id, team_id=conversacion.team_id, operador_id=conversacion.operador_id,
        )
        aplicadas = conversacion.etiquetas_aplicadas.select_related("etiqueta", "aplicada_por")
        return Response(ConversacionEtiquetaSerializer(aplicadas, many=True).data, status=201)

    @action(detail=True, methods=["delete"], url_path=r"etiquetas/(?P<etiqueta_id>\d+)")
    def quitar_etiqueta(self, request, pk=None, etiqueta_id=None):
        require_perm(request, "conversations.change_conversacion")
        conversacion = self.get_object()
        borradas, _ = conversacion.etiquetas_aplicadas.filter(etiqueta_id=etiqueta_id).delete()
        if not borradas:
            raise NotFound("Esa etiqueta no está aplicada a esta conversación.")
        notificar_evento(
            tipo="conversacion_actualizada", organization_id=conversacion.organization_id,
            conversacion_id=conversacion.id, team_id=conversacion.team_id, operador_id=conversacion.operador_id,
        )
        return Response(status=204)

    @action(detail=True, methods=["get", "post"], url_path="observaciones")
    def observaciones(self, request, pk=None):
        """Notas de texto libre sobre esta conversación — se pueden cargar
        en cualquier momento (a diferencia de las que `etiquetas` crea
        automáticamente al resolver/rechazar/pausar, éstas son opcionales)."""
        conversacion = self.get_object()
        if request.method == "GET":
            require_perm(request, "conversations.view_conversacion")
            observaciones = conversacion.observaciones.select_related("operador")
            return Response(ConversacionObservacionSerializer(observaciones, many=True).data)

        require_perm(request, "conversations.change_conversacion")
        entrada = ObservacionInputSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        observacion = ConversacionObservacion.objects.create(
            conversacion=conversacion, operador=request.user, texto=entrada.validated_data["texto"].strip(),
        )
        return Response(ConversacionObservacionSerializer(observacion).data, status=201)

    @action(detail=True, methods=["get", "post"], url_path="notas-internas")
    def notas_internas(self, request, pk=None):
        """Hilo de mensajería ENTRE OPERADORES sobre esta conversación —
        nunca sale hacia Channel Gateway ni la ve el contacto, a diferencia
        de `mensajes`. Ver el docstring de `models.py` para el alcance
        acotado de esto respecto del "chat interno" más genérico que
        documentaba la Fase 4 (Conversation Engine)."""
        conversacion = self.get_object()
        if request.method == "GET":
            require_perm(request, "conversations.view_conversacion")
            notas = conversacion.notas_internas.select_related("operador")
            return Response(ConversacionNotaInternaSerializer(notas, many=True).data)

        require_perm(request, "conversations.change_conversacion")
        entrada = NotaInternaInputSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        nota = ConversacionNotaInterna.objects.create(
            conversacion=conversacion, operador=request.user, texto=entrada.validated_data["texto"].strip(),
        )
        notificar_evento(
            tipo="nota_interna_nueva", organization_id=conversacion.organization_id,
            conversacion_id=conversacion.id, team_id=conversacion.team_id, operador_id=conversacion.operador_id,
        )
        return Response(ConversacionNotaInternaSerializer(nota).data, status=201)
