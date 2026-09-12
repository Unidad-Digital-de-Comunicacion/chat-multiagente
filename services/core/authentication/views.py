from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .keys import public_key_to_jwk
from .serializers import CustomTokenObtainPairSerializer


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/ — email + password -> access/refresh JWT (RS256)
    con `org_id`/`rol` en el payload. Throttle propio, más estricto que el
    resto de la API, para dificultar fuerza bruta de contraseñas."""

    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class JWKSView(APIView):
    """GET /api/auth/jwks/ — clave pública de firma en formato JWKS, para que
    los servicios FastAPI verifiquen el JWT sin compartir ningún secreto."""

    permission_classes = [AllowAny]

    def get(self, request):
        verifying_key = settings.SIMPLE_JWT["VERIFYING_KEY"]
        if not verifying_key:
            return Response({"keys": []})
        return Response({"keys": [public_key_to_jwk(verifying_key)]})
