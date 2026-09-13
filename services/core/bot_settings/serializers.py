from rest_framework import serializers

from .models import BotMessages

_CAMPOS_CON_DEFAULT = [
    "mensaje_bienvenida", "saludo_inicial", "saludo_area", "mensaje_despedida",
    "derivacion_texto", "derivacion_mensaje", "mensaje_cierre_inactividad",
    "mensaje_operador_toma",
]


class BotMessagesSerializer(serializers.ModelSerializer):
    """`valores_efectivos` muestra, para cada campo de texto, lo que el bot
    va a usar realmente (el valor cargado o, si está vacío, el default de
    `bot_settings.defaults`) — así el panel puede mostrar el placeholder
    real en vez de dejar el campo vacío sin explicación."""

    valores_efectivos = serializers.SerializerMethodField()

    class Meta:
        model = BotMessages
        fields = [
            "menu_activo",
            "mensaje_bienvenida", "saludo_inicial", "saludo_area", "mensaje_despedida",
            "derivacion_texto", "derivacion_mensaje", "mensaje_cierre_inactividad",
            "mensaje_operador_toma",
            "minutos_inactividad_cierre", "segundos_remostrar_menu",
            "valores_efectivos", "updated_at",
        ]
        read_only_fields = ["valores_efectivos", "updated_at"]

    def get_valores_efectivos(self, obj):
        return {campo: obj.valor_o_default(campo) for campo in _CAMPOS_CON_DEFAULT}
