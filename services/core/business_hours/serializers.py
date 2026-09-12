from rest_framework import serializers

from .models import DiaExcepcional, HorarioAtencion


class HorarioAtencionSerializer(serializers.ModelSerializer):
    class Meta:
        model = HorarioAtencion
        fields = ["id", "dia_semana", "hora_inicio", "hora_fin", "activo"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        inicio = attrs.get("hora_inicio", getattr(self.instance, "hora_inicio", None))
        fin = attrs.get("hora_fin", getattr(self.instance, "hora_fin", None))
        if inicio and fin and inicio >= fin:
            raise serializers.ValidationError("hora_inicio debe ser anterior a hora_fin.")
        return attrs


class DiaExcepcionalSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiaExcepcional
        fields = [
            "id", "fecha", "tipo", "hora_inicio", "hora_fin",
            "descripcion", "sincronizado", "organization",
        ]
        read_only_fields = ["id", "sincronizado", "organization"]
        # `organization=None` (catálogo compartido de feriados) sólo lo puede
        # escribir la sincronización/plataforma, nunca esta API de tenant.

    def validate(self, attrs):
        tipo = attrs.get("tipo", getattr(self.instance, "tipo", None))
        if tipo == DiaExcepcional.Tipo.HORARIO_REDUCIDO:
            inicio = attrs.get("hora_inicio", getattr(self.instance, "hora_inicio", None))
            fin = attrs.get("hora_fin", getattr(self.instance, "hora_fin", None))
            if not inicio or not fin:
                raise serializers.ValidationError(
                    "Horario reducido necesita hora_inicio y hora_fin."
                )
        return attrs


class HorarioHabilSerializer(serializers.Serializer):
    en_horario = serializers.BooleanField()
    proxima_apertura = serializers.DateTimeField(allow_null=True)
