from rest_framework import serializers

from .models import ChequeoSalud, Incidente


class IncidenteSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    resuelto_por_email = serializers.EmailField(source="resuelto_por.email", read_only=True, default=None)

    class Meta:
        model = Incidente
        fields = [
            "id", "tipo", "tipo_display", "estado", "estado_display", "servicio", "titulo", "detalle",
            "request_ids", "ocurrencias", "primera_vez", "ultima_vez", "notificado_at", "resuelto_at",
            "resuelto_por_email",
        ]
        # Lo único editable a mano es el estado (resolver / reabrir).
        read_only_fields = [f for f in fields if f != "estado"]


class ChequeoSaludSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChequeoSalud
        fields = ["nombre", "url", "ok", "fallos_consecutivos", "ultimo_detalle", "ultimo_chequeo_at"]


class LineaLogSerializer(serializers.Serializer):
    ts = serializers.DateTimeField()
    level = serializers.CharField()
    service = serializers.CharField()
    logger = serializers.CharField()
    msg = serializers.CharField()
    request_id = serializers.CharField()
    exc = serializers.CharField()
