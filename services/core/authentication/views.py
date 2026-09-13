import logging

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from users.models import User

from .keys import public_key_to_jwk
from .models import LoginLockout
from .serializers import (
    CustomTokenObtainPairSerializer, PasswordResetConfirmSerializer, PasswordResetRequestSerializer,
    UsernameResetRequestSerializer,
)
from .utils import get_client_ip

logger = logging.getLogger("authentication")

MAX_INTENTOS_FALLIDOS = 3
HORAS_BLOQUEO = 12
token_generator = PasswordResetTokenGenerator()


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/ — email + password -> access/refresh JWT (RS256)
    con `org_id`/`grupos` en el payload. Throttle propio (más estricto que el
    resto de la API) + bloqueo por IP: a la 3ra falla seguida desde la misma
    IP, se bloquea 12hs (ver `authentication.models.LoginLockout`). El
    bloqueo es un control aparte del throttle — el throttle limita ráfagas
    en una ventana corta, el bloqueo es la penalización explícita que pidió
    el negocio ante fuerza bruta sostenida."""

    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request, *args, **kwargs):
        ip = get_client_ip(request)
        lockout, _ = LoginLockout.objects.get_or_create(ip_address=ip) if ip else (None, False)

        if lockout and lockout.is_blocked:
            return Response(
                {
                    "detail": "Demasiados intentos fallidos desde esta IP. Probá de nuevo más tarde.",
                    "blocked_until": lockout.blocked_until,
                },
                status=429,
            )

        try:
            # `TokenObtainPairView.post` levanta la excepción (401/400) en vez
            # de devolverla como Response — si no se atrapa acá, se escapa
            # directo a `dispatch()` y el código de más abajo nunca corre.
            response = super().post(request, *args, **kwargs)
        except Exception:
            if lockout:
                lockout.registrar_fallo(max_intentos=MAX_INTENTOS_FALLIDOS, horas_bloqueo=HORAS_BLOQUEO)
            raise

        if lockout:
            lockout.registrar_exito()
        return response


class JWKSView(APIView):
    """GET /api/auth/jwks/ — clave pública de firma en formato JWKS, para que
    los servicios FastAPI verifiquen el JWT sin compartir ningún secreto."""

    permission_classes = [AllowAny]

    def get(self, request):
        verifying_key = settings.SIMPLE_JWT["VERIFYING_KEY"]
        if not verifying_key:
            return Response({"keys": []})
        return Response({"keys": [public_key_to_jwk(verifying_key)]})


class PasswordResetRequestView(APIView):
    """POST /api/auth/password-reset/ — pide el email y, si corresponde a una
    cuenta activa, le manda un link para elegir una contraseña nueva.
    Siempre devuelve el mismo mensaje genérico exista o no esa cuenta (evita
    que alguien use este endpoint para averiguar qué emails están
    registrados)."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = token_generator.make_token(user)
            link = f"{settings.FRONTEND_URL}/restablecer-contrasena/{uid}/{token}"
            try:
                send_mail(
                    subject="Restablecer tu contraseña",
                    message=(
                        f"Hola,\n\nPara elegir una contraseña nueva, entrá a este link "
                        f"(válido por un tiempo limitado):\n\n{link}\n\n"
                        "Si no pediste esto, podés ignorar este mensaje."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
            except Exception:
                logger.exception("No se pudo enviar el mail de reset de contraseña a %s", user.email)

        return Response({"detail": "Si el email está registrado, te enviamos instrucciones para restablecer la contraseña."})


class UsernameResetRequestView(APIView):
    """POST /api/auth/username-reset/ — pide el DNI y, si coincide con una
    cuenta activa, le manda un mail A ESA CUENTA recordándole su email (que
    es su usuario de login). No devuelve el email en la respuesta HTTP: eso
    permitiría a cualquiera con un DNI (no siempre secreto) pescar qué email
    tiene asociado; mandarlo al propio email en vez de devolverlo exige
    tener acceso a esa casilla, igual que el reset de contraseña. Mismo
    mensaje genérico exista o no el DNI."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "username_reset"

    def post(self, request):
        serializer = UsernameResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dni = serializer.validated_data["dni"].strip()

        user = User.objects.filter(dni=dni, is_active=True).first() if dni else None
        if user:
            try:
                send_mail(
                    subject="Tu usuario registrado",
                    message=(
                        f"Hola,\n\nPediste recuperar tu usuario. El email con el que estás "
                        f"registrado (y con el que ingresás) es:\n\n{user.email}\n\n"
                        "Si no pediste esto, podés ignorar este mensaje."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
            except Exception:
                logger.exception("No se pudo enviar el mail de recuperación de usuario a %s", user.email)

        return Response({"detail": "Si el DNI está registrado, te enviamos un mail con tu usuario."})


class PasswordResetConfirmView(APIView):
    """POST /api/auth/password-reset-confirm/ — `uid` + `token` (del link del
    mail) + `new_password`. El token es de un solo uso por
    `PasswordResetTokenGenerator` (incluye el hash de la contraseña actual,
    así que deja de servir apenas se usa una vez)."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            uid = force_str(urlsafe_base64_decode(data["uid"]))
            user = User.objects.get(pk=uid, is_active=True)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            user = None

        if user is None or not token_generator.check_token(user, data["token"]):
            raise ValidationError({"token": ["El link no es válido o ya venció. Pedí uno nuevo."]})

        user.set_password(data["new_password"])
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        return Response({"ok": True})
