from rest_framework import serializers

from .models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id", "name", "slug", "plan", "connection_limit",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "slug", "plan", "connection_limit", "is_active", "created_at", "updated_at"]
        # El plan/límite de conexiones los administra la plataforma (billing),
        # no el Admin de la organización — por eso son de solo lectura acá.
