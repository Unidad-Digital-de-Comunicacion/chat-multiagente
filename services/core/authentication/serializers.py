from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Agrega `org_id` y `rol` al payload del JWT (sección 9 de
    docs/CONTEXTO_PROYECTO.md): son los dos claims que Channel Gateway,
    Conversation Engine, Operators Desk y Analytics necesitan para aplicar el
    scoping multi-tenant sin volver a golpear a Core en cada request."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["org_id"] = user.organization_id
        token["rol"] = user.role
        token["email"] = user.email
        return token
