from rest_framework import serializers

from .models import MenuOpcion


class MenuOpcionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuOpcion
        fields = [
            "id", "texto", "slug", "parent", "orden", "tipo",
            "respuesta_texto", "team", "activo", "created_by", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_by", "created_at", "updated_at"]

    def validate(self, attrs):
        tipo = attrs.get("tipo", getattr(self.instance, "tipo", None))
        team = attrs.get("team", getattr(self.instance, "team", None))
        respuesta_texto = attrs.get("respuesta_texto", getattr(self.instance, "respuesta_texto", ""))
        parent = attrs.get("parent", getattr(self.instance, "parent", None))

        if tipo == MenuOpcion.Tipo.DERIVACION and not team:
            raise serializers.ValidationError({"team": "Una opción de tipo Derivación necesita un equipo."})
        if tipo == MenuOpcion.Tipo.RESPUESTA and not (respuesta_texto or "").strip():
            raise serializers.ValidationError({"respuesta_texto": "Una opción de tipo Respuesta necesita un texto."})

        organization_id = self.context["request"].user.organization_id
        if parent and parent.organization_id != organization_id:
            raise serializers.ValidationError({"parent": "El menú padre debe ser de tu organización."})
        if team and team.organization_id != organization_id:
            raise serializers.ValidationError({"team": "El equipo debe ser de tu organización."})
        return attrs


class MenuOpcionTreeSerializer(serializers.ModelSerializer):
    """Vista de sólo lectura del árbol completo, anidada, para el editor del
    Admin Panel. `hijos` recursivo — se arma en memoria en la vista a partir
    de un único queryset (ver menu.views.MenuOpcionViewSet.tree) para no
    disparar una query por nodo."""

    hijos = serializers.SerializerMethodField()

    class Meta:
        model = MenuOpcion
        fields = [
            "id", "texto", "slug", "orden", "tipo", "respuesta_texto",
            "team", "activo", "hijos",
        ]

    def get_hijos(self, obj):
        hijos = self.context["por_padre"].get(obj.id, [])
        return MenuOpcionTreeSerializer(hijos, many=True, context=self.context).data
