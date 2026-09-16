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


class ConversacionSerializer(serializers.ModelSerializer):
    contact = ContactSerializer(read_only=True)
    canal_display = serializers.CharField(source="get_canal_display", read_only=True)
    operador_email = serializers.CharField(source="operador.email", read_only=True, default=None)
    team_nombre = serializers.CharField(source="team.name", read_only=True, default=None)
    estado_operativo = serializers.SerializerMethodField()

    class Meta:
        model = Conversacion
        fields = [
            "id", "contact", "canal", "canal_display", "operador", "operador_email", "team",
            "team_nombre", "menu_finalizado", "bloqueada_hasta", "estado", "estado_operativo",
            "iniciada_at", "cerrada_at", "updated_at",
        ]
        read_only_fields = fields

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


class ConversacionEtiquetaSerializer(serializers.ModelSerializer):
    etiqueta = EtiquetaSerializer(read_only=True)
    aplicada_por_email = serializers.CharField(source="aplicada_por.email", read_only=True, default=None)

    class Meta:
        model = ConversacionEtiqueta
        fields = ["id", "etiqueta", "aplicada_por_email", "aplicada_at"]
        read_only_fields = fields


class AplicarEtiquetaInputSerializer(serializers.Serializer):
    etiqueta = serializers.IntegerField()
    observacion = serializers.CharField(required=False, allow_blank=True, default="")


class ConversacionObservacionSerializer(serializers.ModelSerializer):
    operador_email = serializers.CharField(source="operador.email", read_only=True, default=None)

    class Meta:
        model = ConversacionObservacion
        fields = ["id", "operador_email", "texto", "creado_at"]
        read_only_fields = fields


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
