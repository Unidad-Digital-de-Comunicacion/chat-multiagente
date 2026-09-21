from datetime import timedelta

from channels.models import Canal
from django.utils import timezone
from rest_framework import serializers
from tags.serializers import EtiquetaSerializer

from .models import (
    Contact, Conversacion, ConversacionEtiqueta, ConversacionLog, ConversacionNotaInterna, ConversacionObservacion,
)


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ["id", "canal", "identificador_externo", "nombre"]
        read_only_fields = fields


class ConversacionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversacionLog
        fields = ["id", "remitente", "texto", "creado_at"]
        read_only_fields = fields


class HistorialFiltrosSerializer(serializers.Serializer):
    """Query params de `GET .../historial/` (`conversations.views.
    ConversacionViewSet.historial` y `platform_admin.views.
    HistorialConversacionesPlatformView` — mismo shape en las dos, ver
    `conversations.views.aplicar_filtros_historial`). Parsear/validar acá
    en vez de leer `request.query_params` a mano evita un 500 si alguien
    manda `desde=cualquier-cosa` en vez de una fecha real."""

    canal = serializers.ChoiceField(choices=Canal.Tipo.choices, required=False)
    team = serializers.IntegerField(required=False)
    # `BooleanField(required=False)` solo, sin `default=None` explícito, cae
    # en un default implícito de `False` (quirk de DRF pensado para
    # checkboxes de HTML sin marcar) — sin esto, "no vino el filtro" y
    # "vino como false" quedan indistinguibles y el filtro se aplica
    # siempre, aunque nadie lo haya pedido.
    derivada = serializers.BooleanField(required=False, allow_null=True, default=None)
    desde = serializers.DateField(required=False)
    hasta = serializers.DateField(required=False)
    q = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)


class ConversacionEtiquetaSerializer(serializers.ModelSerializer):
    etiqueta = EtiquetaSerializer(read_only=True)
    aplicada_por_email = serializers.CharField(source="aplicada_por.email", read_only=True, default=None)

    class Meta:
        model = ConversacionEtiqueta
        fields = ["id", "etiqueta", "aplicada_por_email", "aplicada_at"]
        read_only_fields = fields


class ConversacionObservacionSerializer(serializers.ModelSerializer):
    operador_email = serializers.CharField(source="operador.email", read_only=True, default=None)

    class Meta:
        model = ConversacionObservacion
        fields = ["id", "operador_email", "texto", "creado_at"]
        read_only_fields = fields


# `ConversacionHistorialSerializer` reusa las dos clases de arriba — tienen
# que estar definidas antes acá (un atributo de clase se evalúa al definir
# la clase, no perezoso), por eso quedaron fuera del orden alfabético que
# tenían el resto de los serializers de acá abajo.
class ConversacionHistorialSerializer(serializers.ModelSerializer):
    """Vista resumida para "Historial de conversaciones" (Admin Panel) — a
    propósito sigue sin incluir `mensajes`/`notas_internas`: el permiso que
    la habilita (`ver_historial_conversacion`) es distinto de
    `view_conversacion` justamente para que un Admin de organización pueda
    auditar inicio/derivación/fin/etiquetas/observaciones sin que eso le
    desbloquee leer el contenido real de los mensajes ni las notas
    operador-a-operador (ver `Conversacion.Meta.permissions`). `etiquetas`/
    `observaciones` sí se incluyen (pedido explícito — auditar quién
    derivó/tomó/etiquetó/dejó una observación es justamente el propósito de
    esta pantalla) reusando los mismos serializers que ya expone `GET
    .../etiquetas/`/`GET .../observaciones/`, sin recortar nada.

    `ultima_actividad`/`vencida_por_inactividad` leen las anotaciones que
    agrega `conversations.views.anotar_ultima_actividad` — este serializer
    asume que el queryset ya pasó por ahí (las dos vistas que lo usan lo
    hacen), no las calcula de cero."""

    contact = ContactSerializer(read_only=True)
    canal_display = serializers.CharField(source="get_canal_display", read_only=True)
    organization_nombre = serializers.CharField(source="organization.name", read_only=True)
    operador_email = serializers.CharField(source="operador.email", read_only=True, default=None)
    team_nombre = serializers.CharField(source="team.name", read_only=True, default=None)
    etiquetas = ConversacionEtiquetaSerializer(source="etiquetas_aplicadas", many=True, read_only=True)
    observaciones = ConversacionObservacionSerializer(many=True, read_only=True)
    ultima_actividad = serializers.DateTimeField(read_only=True)
    vencida_por_inactividad = serializers.SerializerMethodField()

    class Meta:
        model = Conversacion
        fields = [
            "id", "organization_id", "organization_nombre", "contact", "canal", "canal_display",
            "team_nombre", "derivada_at", "operador_email", "estado", "iniciada_at", "cerrada_at",
            "etiquetas", "observaciones", "ultima_actividad", "vencida_por_inactividad",
        ]
        read_only_fields = fields

    def get_vencida_por_inactividad(self, obj):
        # Mismo criterio que `cerrar_conversaciones_inactivas` (el que de
        # verdad la cerraría en la próxima pasada), para que esto nunca
        # marque "Vencida" algo que en los hechos no se va a cerrar solo:
        # ABIERTA, con un umbral real configurado (0/NULL = desactivado) Y
        # sin equipo ni operador — una vez derivada o tomada, se asume que
        # alguien es responsable y ya no cuenta como vencida.
        minutos = getattr(obj, "minutos_inactividad_cierre", None)
        if not minutos or obj.estado != Conversacion.Estado.ABIERTA:
            return False
        if obj.team_id or obj.operador_id:
            return False
        limite = timezone.now() - timedelta(minutes=minutos)
        return obj.ultima_actividad < limite


class ConversacionSerializer(serializers.ModelSerializer):
    contact = ContactSerializer(read_only=True)
    canal_display = serializers.CharField(source="get_canal_display", read_only=True)
    operador_email = serializers.CharField(source="operador.email", read_only=True, default=None)
    team_nombre = serializers.CharField(source="team.name", read_only=True, default=None)
    estado_operativo = serializers.SerializerMethodField()
    etiquetas = serializers.SerializerMethodField()
    ultima_observacion = serializers.SerializerMethodField()

    class Meta:
        model = Conversacion
        fields = [
            "id", "contact", "canal", "canal_display", "operador", "operador_email", "team",
            "team_nombre", "menu_finalizado", "bloqueada_hasta", "estado", "estado_operativo",
            "etiquetas", "ultima_observacion", "iniciada_at", "cerrada_at", "updated_at",
        ]
        read_only_fields = fields

    def get_etiquetas(self, obj):
        # Shape recortado a propósito (sin `aplicada_por`/`aplicada_at`) —
        # esto es para pintar chips en un listado, no el detalle completo
        # que ya da `GET .../etiquetas/` (`ConversacionEtiquetaSerializer`).
        # `.all()` reusa el `Prefetch` de `ConversacionViewSet.get_queryset`
        # (select_related con la etiqueta), no dispara una query nueva.
        return [
            {
                "id": aplicada.etiqueta_id, "nombre": aplicada.etiqueta.nombre,
                "color": aplicada.etiqueta.color, "color_texto": aplicada.etiqueta.color_texto,
            }
            for aplicada in obj.etiquetas_aplicadas.all()
        ]

    def get_ultima_observacion(self, obj):
        # `.all()` reusa el `Prefetch` (ordenado `-creado_at`) de
        # `ConversacionViewSet.get_queryset` — tomar la primera alcanza,
        # sin pedir de nuevo a la base.
        observaciones = obj.observaciones.all()
        if not observaciones:
            return None
        ultima = observaciones[0]
        return {
            "texto": ultima.texto,
            "operador_email": ultima.operador.email if ultima.operador_id else None,
            "creado_at": ultima.creado_at,
        }

    def get_estado_operativo(self, obj):
        """Vista rápida de "en qué punto del ciclo de vida está" que no
        depende de que el cliente sincronice a mano ninguna de las 3
        etiquetas de sistema "objetivas" (pendiente/asignada/tomada) — se
        calcula sola de `estado`/`team`/`operador`, que ya son la fuente de
        verdad real de esos 3 pasos. Las etiquetas de sistema restantes
        (en_proceso/en_pausa/rechazado/resuelto) SÍ son una decisión del
        operador, no algo derivable — para esas, ver `etiquetas_aplicadas`/
        `GET .../etiquetas/`."""
        if obj.estado == Conversacion.Estado.CERRADA:
            return "cerrada"
        if obj.operador_id:
            return "tomada"
        if obj.team_id:
            return "asignada"
        return "pendiente"


class AplicarEtiquetaInputSerializer(serializers.Serializer):
    etiqueta = serializers.IntegerField()
    observacion = serializers.CharField(required=False, allow_blank=True, default="")


class ObservacionInputSerializer(serializers.Serializer):
    texto = serializers.CharField(allow_blank=False, trim_whitespace=True)


class ConversacionNotaInternaSerializer(serializers.ModelSerializer):
    operador_email = serializers.CharField(source="operador.email", read_only=True, default=None)

    class Meta:
        model = ConversacionNotaInterna
        fields = ["id", "operador_email", "texto", "creado_at"]
        read_only_fields = fields


class NotaInternaInputSerializer(serializers.Serializer):
    texto = serializers.CharField(allow_blank=False, trim_whitespace=True)


class DerivarInputSerializer(serializers.Serializer):
    team = serializers.IntegerField()
    observacion = serializers.CharField(allow_blank=False, trim_whitespace=True)
