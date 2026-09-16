"""Configuración por variables de entorno — ver docker-compose.yml,
servicio `conversation-engine`, y `.env.example` (`CONVERSATION_ENGINE_
SERVICE_TOKEN` del lado de Core). Nada de esto tiene default de
producción a propósito para el secreto — sólo para URLs internas de dev,
mismo criterio que `channel-gateway/app/config.py`."""
import os
from functools import lru_cache


class Settings:
    def __init__(self):
        # JWKS público de Core (RS256) para validar el JWT que manda un
        # operador al conectarse — mismo env var que ya comparten los demás
        # servicios FastAPI (ancla `fastapi-common` en docker-compose.yml).
        self.jwt_public_key_url: str = os.environ.get(
            "JWT_PUBLIC_KEY_URL", "http://core:80/api/auth/jwks/",
        )

        # El secreto que este servicio comparte con Core — Core lo manda en
        # `Authorization: Service-Token <token>` al avisar un evento nuevo
        # (`POST /internal/eventos/`). Se genera desde el Admin Panel:
        # Plataforma > Tokens de servicios internos > Conversation Engine >
        # Generar, y se pega en `CONVERSATION_ENGINE_SERVICE_TOKEN` del
        # `.env` de la raíz del repo (docker-compose.yml lo pasa acá adentro
        # ya con este nombre).
        self.core_service_token: str = os.environ.get("CORE_SERVICE_TOKEN", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
