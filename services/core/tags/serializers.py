from rest_framework import serializers

from .models import HEX_RE, Etiqueta


class EtiquetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Etiqueta
        fields = ["id", "team", "codigo", "nombre", "color", "es_sistema", "orden", "created_at", "updated_at"]
        read_only_fields = ["id", "codigo", "es_sistema", "created_at", "updated_at"]

    def validate_color(self, value):
        if not HEX_RE.match(value):
            raise serializers.ValidationError("El color debe ser hexadecimal, ej: #3454D1.")
        return value.upper()

    def validate_nombre(self, value):
        if self.instance and self.instance.es_sistema and value != self.instance.nombre:
            raise serializers.ValidationError(
                "El nombre de una etiqueta del sistema no se puede modificar, sólo su color."
            )
        return value

    def validate_team(self, team):
        if team is None:
            return team
        request = self.context.get("request")
        if request and team.organization_id != request.user.organization_id:
            raise serializers.ValidationError("El equipo debe ser de tu organización.")
        return team
