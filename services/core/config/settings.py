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
    "common",
    "authentication",
    "organizations",
    "users",
    "teams",
    "business_hours",
    "menu",
    "bot_settings",
    "tags",
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
        "DIRS": [],
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
