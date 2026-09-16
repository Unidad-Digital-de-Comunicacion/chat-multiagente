from django.conf import settings

from rest_framework import serializers

from .models import Canal


class CanalSerializer(serializers.ModelSerializer):
    """`api_key` es write-only: se puede cargar/reemplazar pero no viaja de
    vuelta por ESE campo. `api_key_configurada` (bool) y `api_key_preview`
    (los últimos 4 caracteres, ej. "••••3f9a") siguen para el caso normal
    de sólo confirmar que se cargó la correcta.

    `api_key_valor` es la excepción deliberada, pedida a mano: devuelve el
    valor COMPLETO en texto plano — a diferencia de `webhook_secret` (que
    Core genera y por eso siempre se puede mostrar entero sin riesgo),
    esto SÍ es una credencial externa real de Meta, así que cualquiera con
    `channels.view_canal` puede llegar a verla. Se mantiene igual el resto
    del patrón write-only/preview de acá arriba por si en algún momento se
    quiere volver a ocultarlo — el Admin Panel es el único que decide
    mostrarlo o no (botón "Mostrar", `ChannelsPage.tsx`).

    `webhook_url`/`webhook_secret` vienen `None` para Webchat (no usa el
    webhook de Meta, ver `Canal.TIPOS_CON_WEBHOOK_META`)."""

    api_key = serializers.CharField(required=False, allow_blank=True, write_only=True)
    api_key_configurada = serializers.SerializerMethodField()
    api_key_preview = serializers.SerializerMethodField()
    api_key_valor = serializers.SerializerMethodField()
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    webhook_url = serializers.SerializerMethodField()
    webhook_secret = serializers.SerializerMethodField()

    class Meta:
        model = Canal
        fields = [
            "id", "tipo", "tipo_display", "api_key", "api_key_configurada", "api_key_preview",
            "api_key_valor", "telefono_id", "waba_id", "webhook_url", "webhook_secret", "activo",
            "ultimo_chequeo_at", "ultimo_chequeo_ok", "ultimo_chequeo_detalle", "updated_at",
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

    def get_api_key_valor(self, obj):
        return obj.api_key or None

    def get_webhook_url(self, obj):
        if obj.tipo not in Canal.TIPOS_CON_WEBHOOK_META:
            return None
        return f"{settings.CHANNEL_GATEWAY_PUBLIC_URL}/webhooks/{obj.tipo.lower()}/{obj.uuid}/"

    def get_webhook_secret(self, obj):
        if obj.tipo not in Canal.TIPOS_CON_WEBHOOK_META:
            return None
        return obj.webhook_secret
