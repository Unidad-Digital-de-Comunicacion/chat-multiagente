from rest_framework import serializers

from .models import HEX_RE, Etiqueta


class EtiquetaSerializer(serializers.ModelSerializer):
    """`team` es de sólo lectura: nunca se elige a mano — lo asigna
    `defaults.asegurar_etiquetas_equipo` una única vez por equipo ("cada
    equipo es una etiqueta"). Toda etiqueta que arma un Admin a mano es
    general (`team=None`)."""

    class Meta:
        model = Etiqueta
        fields = [
            "id", "team", "codigo", "nombre", "color", "color_texto", "es_sistema", "orden",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "team", "codigo", "es_sistema", "created_at", "updated_at"]

    def _validar_hex(self, value):
        if not HEX_RE.match(value):
            raise serializers.ValidationError("El color debe ser hexadecimal, ej: #3454D1.")
        return value.upper()

    def validate_color(self, value):
        return self._validar_hex(value)

    def validate_color_texto(self, value):
        return self._validar_hex(value)

    def validate_nombre(self, value):
        instance = self.instance
        if instance and (instance.es_sistema or instance.team_id) and value != instance.nombre:
            raise serializers.ValidationError(
                "El nombre de una etiqueta de sistema o de equipo no se puede modificar, sólo su color "
                "(la de equipo se renombra sola si renombrás el equipo)."
            )
        return value
