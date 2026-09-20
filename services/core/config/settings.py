"""
Configuración del Core Platform Service (Django + DRF).

Fuente de verdad del negocio: organizaciones, usuarios/roles, equipos,
horarios de atención y árbol de menú (ver docs/CONTEXTO_PROYECTO.md).
"""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _env_list(name, default=""):
    raw = os.environ.get(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-secret-key-change-me")
DEBUG = _env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    "drf_spectacular_sidecar",
    "common",
    "authentication",
    "organizations",
    "users",
    "teams",
    "business_hours",
    "menu",
    "bot_settings",
    "tags",
    "channels",
    "platform_admin",
    "conversations",
]

AUTH_USER_MODEL = "users.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        # Contenido legal estático (`config/views.py::privacy_policy`) — no
        # amerita una app Django propia sólo para esto.
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --------------------------------------------------------------------------- #
# Base de datos: una única instancia de Postgres compartida por todos los
# microservicios, un esquema por servicio (search_path). Ver sección 1 y 7 de
# docs/CONTEXTO_PROYECTO.md.
# --------------------------------------------------------------------------- #
DB_SCHEMA = os.environ.get("DB_SCHEMA", "core")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "chatplatform"),
        "USER": os.environ.get("DB_USER", "chatplatform"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "changeme"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "OPTIONS": {
            "options": f"-c search_path={DB_SCHEMA},public",
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------- #
# Separación back/front: CORS acotado a los orígenes configurados (los
# frontends React), autenticación stateless por JWT (sin cookies de sesión
# para la API) y throttling básico contra abuso. Ver la skill
# `chat-security-review` para el detalle de por qué.
# --------------------------------------------------------------------------- #
CORS_ALLOWED_ORIGINS = _env_list("FRONTEND_ORIGINS", "http://localhost:3000,http://localhost:3001")
CORS_ALLOW_CREDENTIALS = False

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        # Autenticación de los OTROS microservicios (Channel Gateway, etc.)
        # contra la API de Core — ver `platform_admin.service_auth`. Global
        # a propósito (no sólo en las vistas internas) para que un endpoint
        # cualquiera pueda optar a futuro por aceptar también un
        # `ServiceToken`; no interfiere con el login de usuarios porque sólo
        # reacciona al esquema `Service-Token`, nunca a `Bearer`.
        "platform_admin.service_auth.ServiceTokenAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "20/minute",
        "user": "300/minute",
        "login": "10/minute",
        "password_reset": "5/hour",
        "username_reset": "5/hour",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# Esquema/documentación autogenerada de la API de Core (sección "Plataforma"
# del Admin Panel, "Manuales y API" — sólo el superusuario real la puede ver,
# `platform_admin.views` fija `permission_classes=[IsPlatformSuperuser]` a
# mano en cada vista de drf-spectacular en vez de dejar el default AllowAny).
SPECTACULAR_SETTINGS = {
    "TITLE": "Chat Multiagente — API de Core",
    "DESCRIPTION": "Referencia autogenerada de la API del microservicio Core (autenticación, "
                    "organizaciones, usuarios, equipos, horarios, menú, mensajes del bot, etiquetas "
                    "y canales). Es sólo la API de Core — Channel Gateway/Conversation "
                    "Engine/Operators Desk/Analytics todavía son stubs de Fase 0.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Por default Swagger/Redoc cargan su JS/CSS desde jsdelivr.net — en un
    # entorno sin salida a internet (o con esa CDN bloqueada) la página
    # queda en blanco sin ningún error visible. `drf-spectacular-sidecar`
    # empaqueta esos mismos assets como estáticos de Django (los sirve
    # nginx desde /static/, los junta `collectstatic` del entrypoint) para
    # que el visor funcione 100% local, sin depender de ninguna CDN.
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
}

# --------------------------------------------------------------------------- #
# Email: recuperación de contraseña. Backend "console" en dev/tests — el
# link de reset queda impreso en los logs del contenedor `core`, no se manda
# a ningún lado de verdad, hasta que se configure un SMTP real. Cambiar
# EMAIL_BACKEND a "django.core.mail.backends.smtp.EmailBackend" y completar
# EMAIL_HOST/PORT/USER/PASSWORD/USE_TLS cuando haya un proveedor real.
# --------------------------------------------------------------------------- #
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = _env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-responder@chatplatform.local")

# URL pública del Admin Panel (React) — para armar el link de
# /restablecer-contrasena/<uid>/<token> que se manda por mail.
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# URL pública de Channel Gateway — para armar `webhook_url` en
# `channels.CanalSerializer` (la que el Admin pega en la configuración del
# webhook de Meta). Puerto 8002 en dev (docker-compose); en producción es el
# dominio público real del servicio, no la URL interna `http://channel-
# gateway:8000` que usa Core para llamarlo puerta adentro de la red.
CHANNEL_GATEWAY_PUBLIC_URL = os.environ.get("CHANNEL_GATEWAY_PUBLIC_URL", "http://localhost:8002").rstrip("/")

# URL INTERNA (red de docker-compose) para que Core le pida a Channel
# Gateway que mande un mensaje saliente (`conversations.channel_gateway_
# client.enviar_mensaje_saliente`, `POST /messages/send`) — a diferencia de
# `CHANNEL_GATEWAY_PUBLIC_URL` de acá arriba (la que ve el navegador/Meta),
# ésta es la que usa Core mismo, puerta adentro de la red de contenedores.
CHANNEL_GATEWAY_INTERNAL_URL = os.environ.get("CHANNEL_GATEWAY_INTERNAL_URL", "http://channel-gateway:8000").rstrip("/")

# URL INTERNA de Conversation Engine — Core le avisa ahí (`conversations.
# conversation_engine_client.notificar_evento`) cada vez que pasa algo que
# un operador conectado por WebSocket necesita saber en tiempo real (nueva
# conversación/mensaje, tomada, derivada, cerrada, etiqueta o nota interna
# nueva). Mismo patrón que `CHANNEL_GATEWAY_INTERNAL_URL` de acá arriba
# (dirección Core -> servicio FastAPI, puerta adentro de la red).
CONVERSATION_ENGINE_INTERNAL_URL = os.environ.get(
    "CONVERSATION_ENGINE_INTERNAL_URL", "http://conversation-engine:8000",
).rstrip("/")

# App de Meta (misma app/credenciales que ya usa channel-gateway para
# verificar firmas de webhook, `META_APP_SECRET`) — acá hace falta además
# para `channels.embedded_signup`: el intercambio de `code` por
# `access_token` del Embedded Signup de WhatsApp se hace del lado de Core
# (dueño de `Canal`), no de Channel Gateway.
META_APP_ID = os.environ.get("META_APP_ID", "")
META_APP_SECRET = os.environ.get("META_APP_SECRET", "")

# Excepción real confirmada en producción (2026-09-18, ver channels/
# health.py): Instagram puede quedar dado de alta bajo una app de Meta
# DISTINTA a la de arriba — ahí `/debug_token` (el chequeo de conexión) y la
# verificación de firma de channel-gateway necesitan las credenciales de ESA
# otra app, no las de WhatsApp/Messenger. Sin configurar, cae en las de
# arriba (mismo comportamiento de antes, para el caso común de una sola app).
META_APP_ID_INSTAGRAM = os.environ.get("META_APP_ID_INSTAGRAM", "") or META_APP_ID
META_APP_SECRET_INSTAGRAM = os.environ.get("META_APP_SECRET_INSTAGRAM", "") or META_APP_SECRET

# --------------------------------------------------------------------------- #
# JWT (RS256): Core firma con la clave privada; todos los servicios (FastAPI
# incluidos) validan con la pública, publicada en /api/auth/jwks/. Evita tener
# que distribuir un secreto compartido a cada microservicio.
# --------------------------------------------------------------------------- #
JWT_PRIVATE_KEY_PATH = os.environ.get("JWT_PRIVATE_KEY_PATH", str(BASE_DIR / "keys" / "jwt_private.pem"))
JWT_PUBLIC_KEY_PATH = os.environ.get("JWT_PUBLIC_KEY_PATH", str(BASE_DIR / "keys" / "jwt_public.pem"))


def _read_key(path):
    try:
        return Path(path).read_text()
    except FileNotFoundError:
        # Las claves las genera `manage.py generate_jwt_keys` (lo corre
        # entrypoint.sh antes de levantar el servidor). En collectstatic/tests
        # fuera de ese flujo, seguir sin romper el import de settings.
        return ""


SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": False,
    "ALGORITHM": "RS256",
    "SIGNING_KEY": _read_key(JWT_PRIVATE_KEY_PATH),
    "VERIFYING_KEY": _read_key(JWT_PUBLIC_KEY_PATH),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}
