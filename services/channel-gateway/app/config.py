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

        # Secreto de la app de Meta (Facebook Developers) usado para firmar
        # CADA webhook que manda (header `X-Hub-Signature-256`) — pensado
        # como uno solo para toda la plataforma (una app de Meta para
        # WhatsApp+Messenger+Instagram), a diferencia de `webhook_secret`
        # (por canal, el "verify token" del handshake `GET`).
        self.meta_app_secret: str = os.environ.get("META_APP_SECRET", "")

        # Excepción real confirmada en producción (2026-09-18): Instagram
        # puede quedar dado de alta en el dashboard de Meta bajo una app
        # DISTINTA a la de WhatsApp/Messenger (pasa si se configuró por
        # separado) — ahí la firma de sus webhooks viene calculada con OTRO
        # secreto, y validarla contra `meta_app_secret` siempre da 403 aunque
        # el secreto "principal" esté perfectamente bien cargado (WhatsApp/
        # Messenger seguían validando bien con el mismo secreto mientras
        # Instagram fallaba el 100% de las veces — así se lo detectó). Si no
        # se configura por separado, cae en `meta_app_secret` (mismo
        # comportamiento de antes, para el caso común de una sola app).
        self.meta_app_secret_instagram: str = os.environ.get("META_APP_SECRET_INSTAGRAM", "") or self.meta_app_secret

        self.http_timeout_segundos: float = 10.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
