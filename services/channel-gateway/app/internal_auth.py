"""Gate para endpoints que sólo OTROS servicios internos deberían poder
llamar (hoy: `POST /messages/send`, sin ningún llamador real todavía —
Conversation Engine es Fase 4) — nunca Meta, que sólo llama a `/webhooks/*`
y no necesita (ni debe) tener este secreto.

Reutiliza el mismo `CORE_SERVICE_TOKEN` que este servicio ya usa para
autenticarse CONTRA Core (`core_client.py`) — no hace falta un secreto
aparte sólo para la dirección inversa, y evita sumar una variable de
entorno más para algo que todavía no tiene un consumidor real. Mismo
esquema `Authorization: Service-Token <token>` que `platform_admin.
service_auth.ServiceTokenAuthentication` del lado de Core, por consistencia."""
import hmac

from fastapi import Header, HTTPException

from .config import get_settings

ESQUEMA = "Service-Token"


def requerir_servicio_interno(authorization: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if not settings.core_service_token:
        # Sin token configurado del lado de Channel Gateway, no hay con qué
        # comparar — negar todo en vez de aceptar cualquier cosa (fail closed).
        raise HTTPException(status_code=503, detail="Este servicio no tiene CORE_SERVICE_TOKEN configurado.")
    if not authorization or not authorization.startswith(f"{ESQUEMA} "):
        raise HTTPException(status_code=401, detail="Falta el header Authorization: Service-Token <token>.")
    token = authorization[len(ESQUEMA) + 1:].strip()
    if not hmac.compare_digest(token, settings.core_service_token):
        raise HTTPException(status_code=401, detail="Token inválido.")
