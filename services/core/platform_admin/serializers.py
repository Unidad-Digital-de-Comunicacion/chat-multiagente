from rest_framework import serializers

from .models import MetaAppConfig, ServiceToken


class ServiceTokenSerializer(serializers.ModelSerializer):
    """`token` es write-only, igual que `channels.CanalSerializer.api_key`:
    se puede cargar/reemplazar a mano por PATCH, pero nunca se devuelve por
    la API — sólo si está configurado y sus últimos 4 caracteres (cifrado
    en reposo, ver `ServiceToken.token`). La acción `generar` (ver
    `ServiceTokenViewSet`) es la otra forma de cargarlo, generando uno
    seguro al azar y devolviéndolo en texto plano UNA sola vez en la
    respuesta de esa acción, nunca en éste."""

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


class MetaAppConfigSerializer(serializers.ModelSerializer):
    """`app_secret` write-only, mismo patrón que `channels.CanalSerializer.
    api_key`: se puede cargar/reemplazar por PATCH, nunca se devuelve por
    ESE campo — `app_secret_configurada`/`app_secret_preview` alcanzan para
    el caso normal, y `app_secret_valor` (el valor completo) para cuando
    un superusuario necesita copiarlo/verificarlo entero, igual que
    `api_key_valor`."""

    app_secret = serializers.CharField(required=False, allow_blank=True, write_only=True)
    app_secret_configurada = serializers.SerializerMethodField()
    app_secret_preview = serializers.SerializerMethodField()
    app_secret_valor = serializers.SerializerMethodField()

    class Meta:
        model = MetaAppConfig
        fields = [
            "app_id", "app_secret", "app_secret_configurada", "app_secret_preview", "app_secret_valor",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]

    def get_app_secret_configurada(self, obj):
        return bool(obj.app_secret)

    def get_app_secret_preview(self, obj):
        if not obj.app_secret:
            return None
        return f"••••{obj.app_secret[-4:]}" if len(obj.app_secret) > 4 else "••••"

    def get_app_secret_valor(self, obj):
        return obj.app_secret or None
