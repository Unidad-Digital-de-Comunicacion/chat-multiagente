from django.conf import settings

from rest_framework import serializers

from .models import Canal


class CanalSerializer(serializers.ModelSerializer):
    """`api_key` es write-only: se puede cargar/reemplazar pero nunca se
    devuelve por la API. Para que el Admin Panel pueda mostrar "configurada"
    sin exponer el valor real, se agregan dos campos de sólo lectura:
    `api_key_configurada` (bool) y `api_key_preview` (los últimos 4
    caracteres, ej. "••••3f9a") — sólo con eso alcanza para confirmar que se
    cargó la correcta sin volver a mostrarla entera.

    `webhook_secret` es la excepción a ese criterio: a propósito SÍ se
    devuelve completo (no hay `_preview`/`_configurada`) porque, a
    diferencia de `api_key` (una credencial que el Admin trae de afuera),
    éste lo genera Core — el Admin lo tiene que poder copiar entero para
    pegarlo en la configuración del webhook. `webhook_url`/`webhook_secret`
    vienen `None` para Webchat (no usa el webhook de Meta, ver
    `Canal.TIPOS_CON_WEBHOOK_META`)."""

    api_key = serializers.CharField(required=False, allow_blank=True, write_only=True)
    api_key_configurada = serializers.SerializerMethodField()
    api_key_preview = serializers.SerializerMethodField()
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    webhook_url = serializers.SerializerMethodField()
    webhook_secret = serializers.SerializerMethodField()

    class Meta:
        model = Canal
        fields = [
            "id", "tipo", "tipo_display", "api_key", "api_key_configurada", "api_key_preview",
            "telefono_id", "webhook_url", "webhook_secret", "activo", "ultimo_chequeo_at",
            "ultimo_chequeo_ok", "ultimo_chequeo_detalle", "updated_at",
        ]
        read_only_fields = [
            "id", "tipo", "tipo_display", "ultimo_chequeo_at", "ultimo_chequeo_ok",
            "ultimo_chequeo_detalle", "updated_at",
        ]

    def get_api_key_configurada(self, obj):
        return bool(obj.api_key)

    def get_api_key_preview(self, obj):
        if not obj.api_key:
            return None
        return f"••••{obj.api_key[-4:]}" if len(obj.api_key) > 4 else "••••"

    def get_webhook_url(self, obj):
        if obj.tipo not in Canal.TIPOS_CON_WEBHOOK_META:
            return None
        return f"{settings.CHANNEL_GATEWAY_PUBLIC_URL}/webhooks/{obj.tipo.lower()}/{obj.uuid}/"

    def get_webhook_secret(self, obj):
        if obj.tipo not in Canal.TIPOS_CON_WEBHOOK_META:
            return None
        return obj.webhook_secret
