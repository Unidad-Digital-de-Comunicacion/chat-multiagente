from rest_framework import serializers

from .models import Organization


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id", "name", "slug", "plan", "connection_limit", "user_limit", "monthly_conversation_limit",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "slug", "plan", "connection_limit", "user_limit", "monthly_conversation_limit",
            "is_active", "created_at", "updated_at",
        ]
        # El plan/límites/is_active los administra la plataforma (superusuarios,
        # `PlatformOrganizationSerializer` acá abajo), no el Admin de la propia
        # organización — por eso son de solo lectura en este serializer.


class PlatformOrganizationSerializer(serializers.ModelSerializer):
    """La usa `PlatformOrganizationViewSet` — administración de TODAS las
    organizaciones desde la sección "Plataforma" del Admin Panel
    (`common.permissions.IsPlatformSuperuser`). A diferencia de
    `OrganizationSerializer` de acá arriba (que un Admin de organización usa
    para ver, nunca editar, la suya propia), acá sí son editables: nombre,
    slug, plan, los 3 límites (0 = sin límite) y activo/inactivo.
    `deleted_at` es de sólo lectura — se marca con `DELETE` (soft delete,
    `common.soft_delete`) y se deshace con la action `restaurar`."""

    class Meta:
        model = Organization
        fields = [
            "id", "name", "slug", "plan", "connection_limit", "user_limit", "monthly_conversation_limit",
            "is_active", "deleted_at", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "deleted_at", "created_at", "updated_at"]
