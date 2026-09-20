"""Configuración por variables de entorno (ver `docker-compose.yml`,
servicio `channel-gateway`, y `.env.example`). Nada de esto tiene default de
producción a propósito para los secretos — sólo para URLs internas de dev."""
import os
from functools import lru_cache


class Settings:
    def __init__(self):
        # URL interna (red de docker-compose) para llamar a Core — no
        # confundir con `CHANNEL_GATEWAY_PUBLIC_URL` del lado de Core, que
        # es la URL PÚBLICA de este mismo servicio (la que Meta usa para
        # llamarnos).
        self.core_base_url: str = os.environ.get("CORE_BASE_URL", "http://core:80").rstrip("/")

        # El token que este servicio usa para autenticarse contra Core
        # (`Authorization: Service-Token <token>`) — lo genera un
        # superusuario de plataforma en el Admin Panel (Plataforma > Tokens
        # de servicios internos > Channel Gateway > Generar) y se pega acá.
        # Sin esto no hay forma de leer `api_key`/`webhook_secret` de ningún
        # canal.
        self.core_service_token: str = os.environ.get("CORE_SERVICE_TOKEN", "")

        self.http_timeout_segundos: float = 10.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
