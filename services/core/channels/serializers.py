from rest_framework import serializers

from .models import Canal


class CanalSerializer(serializers.ModelSerializer):
    """`api_key` es write-only: se puede cargar/reemplazar pero nunca se
    devuelve por la API. Para que el Admin Panel pueda mostrar "configurada"
    sin exponer el valor real, se agregan dos campos de sólo lectura:
    `api_key_configurada` (bool) y `api_key_preview` (los últimos 4
    caracteres, ej. "••••3f9a") — sólo con eso alcanza para confirmar que se
    cargó la correcta sin volver a mostrarla entera."""

    api_key = serializers.CharField(required=False, allow_blank=True, write_only=True)
    api_key_configurada = serializers.SerializerMethodField()
    api_key_preview = serializers.SerializerMethodField()
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = Canal
        fields = [
            "id", "tipo", "tipo_display", "api_key", "api_key_configurada", "api_key_preview",
            "activo", "ultimo_chequeo_at", "ultimo_chequeo_ok", "ultimo_chequeo_detalle", "updated_at",
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
