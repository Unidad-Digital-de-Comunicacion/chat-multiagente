from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Agrega `org_id` y `grupos` al payload del JWT (sección 9 de
    docs/CONTEXTO_PROYECTO.md): son los claims que Channel Gateway,
    Conversation Engine, Operators Desk y Analytics necesitan para aplicar el
    scoping multi-tenant sin volver a golpear a Core en cada request. No hay
    un `rol` singular — un usuario puede estar en más de un grupo a la vez
    (ver users.group_permissions)."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["org_id"] = user.organization_id
        token["grupos"] = list(user.groups.values_list("name", flat=True))
        token["email"] = user.email
        return token


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class UsernameResetRequestSerializer(serializers.Serializer):
    dni = serializers.CharField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField()

    def validate_new_password(self, value):
        validate_password(value)
        return value
