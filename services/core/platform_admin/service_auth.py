"""Autenticación de los OTROS microservicios del proyecto contra la API de
Core usando `ServiceToken` (sección "Plataforma" > "Tokens de servicios
internos") en vez del JWT de un usuario humano. Hasta que existió Channel
Gateway de verdad, estos tokens eran sólo configuración sin nada del otro
lado que los validara (ver el docstring de `ServiceToken`) — esto es esa
validación, y Channel Gateway es su primer consumidor real."""
from django.contrib.auth.models import AnonymousUser

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission

from .models import ServiceToken

ESQUEMA = "Service-Token"


class ServiceTokenAuthentication(BaseAuthentication):
    """Header `Authorization: Service-Token <token>` — a propósito un
    esquema distinto de `Bearer` (que ya usa `JWTAuthentication` para
    usuarios humanos) para no confundir un JWT vencido/mal formado con "esto
    no es un microservicio". No hay un `User` de Django detrás de esto:
    `request.user` queda anónimo y el `ServiceToken` ya validado (token
    cargado y `activo=True`) queda en `request.auth`, que es lo único que
    miran los permisos de acá abajo."""

    keyword = ESQUEMA

    def authenticate(self, request):
        header = request.headers.get("Authorization", "")
        if not header.startswith(f"{self.keyword} "):
            return None
        token = header[len(self.keyword) + 1:].strip()
        if not token:
            raise AuthenticationFailed("Falta el token de servicio.")
        try:
            service_token = ServiceToken.objects.get(token=token, activo=True)
        except ServiceToken.DoesNotExist:
            raise AuthenticationFailed("Token de servicio inválido o inactivo.")
        return (AnonymousUser(), service_token)

    def authenticate_header(self, request):
        return self.keyword


class IsChannelGatewayService(BasePermission):
    """Gate de los endpoints internos que sólo Channel Gateway puede llamar
    (ej. `channels.views.InternalCanalConfigView`) — nunca un usuario, ni
    siquiera el superusuario de plataforma vía JWT."""

    def has_permission(self, request, view):
        auth = request.auth
        return bool(isinstance(auth, ServiceToken) and auth.servicio == ServiceToken.Servicio.CHANNEL_GATEWAY)


try:
    from drf_spectacular.extensions import OpenApiAuthenticationExtension

    class ServiceTokenScheme(OpenApiAuthenticationExtension):
        """Sólo para que `platform_admin.PlatformSchemaView` documente el
        esquema `Service-Token` en vez de tirar un warning por cada vista de
        la API (todas heredan `ServiceTokenAuthentication` del default
        global) al no encontrar esto — no cambia nada en runtime."""

        target_class = "platform_admin.service_auth.ServiceTokenAuthentication"
        name = "serviceTokenAuth"

        def get_security_definition(self, auto_schema):
            return {"type": "apiKey", "in": "header", "name": "Authorization", "description": "Service-Token <token>"}
except ImportError:
    pass
