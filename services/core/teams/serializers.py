from rest_framework import serializers

from .models import Team


class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ["id", "name", "members", "is_active", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_members(self, members):
        request = self.context["request"]
        ajenos = [m for m in members if m.organization_id != request.user.organization_id]
        if ajenos:
            raise serializers.ValidationError("Todos los miembros deben pertenecer a la misma organización.")
        return members
