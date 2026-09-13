from rest_framework import serializers

from .models import ServiceToken


class ServiceTokenSerializer(serializers.ModelSerializer):
    """`token` es write-only, igual que `channels.CanalSerializer.api_key`:
    se puede cargar/reemplazar a mano por PATCH, pero nunca se devuelve por
    la API — sólo si está configurado y sus últimos 4 caracteres. La acción
    `generar` (ver `ServiceTokenViewSet`) es la otra forma de cargarlo,
    generando uno seguro al azar y devolviéndolo en texto plano UNA sola vez
    en la respuesta de esa acción, nunca en éste."""

    token = serializers.CharField(required=False, allow_blank=True, write_only=True)
    token_configurado = serializers.SerializerMethodField()
    token_preview = serializers.SerializerMethodField()
    servicio_display = serializers.CharField(source="get_servicio_display", read_only=True)

    class Meta:
        model = ServiceToken
        fields = [
            "id", "servicio", "servicio_display", "token", "token_configurado", "token_preview",
            "activo", "generado_at", "updated_at",
        ]
        read_only_fields = ["id", "servicio", "servicio_display", "generado_at", "updated_at"]

    def get_token_configurado(self, obj):
        return bool(obj.token)

    def get_token_preview(self, obj):
        if not obj.token:
            return None
        return f"••••{obj.token[-4:]}" if len(obj.token) > 4 else "••••"
