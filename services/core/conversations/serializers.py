from rest_framework import serializers

from .models import Contact, Conversacion, ConversacionLog


class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = ["id", "canal", "identificador_externo", "nombre"]
        read_only_fields = fields


class ConversacionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConversacionLog
        fields = ["id", "remitente", "texto", "creado_at"]
        read_only_fields = fields


class ConversacionSerializer(serializers.ModelSerializer):
    contact = ContactSerializer(read_only=True)
    canal_display = serializers.CharField(source="get_canal_display", read_only=True)
    operador_email = serializers.CharField(source="operador.email", read_only=True, default=None)
    team_nombre = serializers.CharField(source="team.name", read_only=True, default=None)

    class Meta:
        model = Conversacion
        fields = [
            "id", "contact", "canal", "canal_display", "operador", "operador_email", "team",
            "team_nombre", "menu_finalizado", "estado", "iniciada_at", "cerrada_at", "updated_at",
        ]
        read_only_fields = fields
