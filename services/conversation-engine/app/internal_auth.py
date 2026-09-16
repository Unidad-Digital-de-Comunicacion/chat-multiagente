"""Gate del único endpoint que sólo Core debería poder llamar
(`POST /internal/eventos/`) — mismo esquema `Authorization: Service-Token
<token>` que `platform_admin.service_auth.ServiceTokenAuthentication` del
lado de Core y que `channel-gateway/app/internal_auth.py`, por
consistencia. El secreto es el que Core generó para el servicio
`CONVERSATION_ENGINE` (Admin Panel > Plataforma > Tokens de servicios
internos) — este servicio lo conoce por su propia variable de entorno
`CORE_SERVICE_TOKEN` (ver `config.py`)."""
import hmac

from fastapi import Header, HTTPException

from .config import get_settings

ESQUEMA = "Service-Token"


def requerir_servicio_interno(authorization: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.core_service_token:
        # Sin token configurado de este lado, no hay con qué comparar —
        # negar todo en vez de aceptar cualquier cosa (fail closed).
        raise HTTPException(status_code=503, detail="Este servicio no tiene CORE_SERVICE_TOKEN configurado.")
    if not authorization or not authorization.startswith(f"{ESQUEMA} "):
        raise HTTPException(status_code=401, detail="Falta el header Authorization: Service-Token <token>.")
    token = authorization[len(ESQUEMA) + 1:].strip()
    if not hmac.compare_digest(token, settings.core_service_token):
        raise HTTPException(status_code=401, detail="Token inválido.")
