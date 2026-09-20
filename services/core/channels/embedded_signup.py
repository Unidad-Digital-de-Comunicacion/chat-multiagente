"""Intercambio de `code` por `access_token` del Embedded Signup de
WhatsApp — el SDK de Facebook en el navegador le da al Admin Panel un
`code` de un solo uso al terminar el popup de alta (junto con `phone_
number_id`/`waba_id`, que vienen del mismo callback, no de acá). Esto
cambia ese `code` por el access_token real contra la Graph API — llamado
desde `CanalViewSet.whatsapp_exchange`, nunca expuesto directo al
frontend (necesita el `app_secret` de `platform_admin.MetaAppConfig`, un
secreto de servidor, editable desde Plataforma)."""
import requests

from platform_admin.models import MetaAppConfig

GRAPH_API_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
TIMEOUT_SEGUNDOS = 10


class IntercambioFallido(Exception):
    def __init__(self, detalle: str):
        self.detalle = detalle
        super().__init__(detalle)


def intercambiar_code_por_token(code: str) -> str:
    app = MetaAppConfig.obtener()
    if not app.app_id or not app.app_secret:
        raise IntercambioFallido("La app de Meta no está configurada en Plataforma.")

    try:
        response = requests.get(
            GRAPH_API_URL,
            params={"client_id": app.app_id, "client_secret": app.app_secret, "code": code},
            timeout=TIMEOUT_SEGUNDOS,
        )
    except requests.RequestException as exc:
        raise IntercambioFallido(f"No se pudo conectar con Meta: {exc}") from exc

    data = response.json() if response.content else {}
    if response.status_code != 200 or "access_token" not in data:
        mensaje = (data.get("error") or {}).get("message") or f"Meta respondió {response.status_code}."
        raise IntercambioFallido(mensaje)
    return data["access_token"]
