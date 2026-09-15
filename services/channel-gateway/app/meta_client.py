"""Envío de mensajes salientes vía la Graph API de Meta — dos formas
distintas, no intercambiables:

- Messenger/Instagram comparten la misma "Send API" (`POST /me/messages`
  con `{recipient: {id}, message: {text}}`, autenticación por query param
  `access_token`).
- WhatsApp usa la Cloud API (`POST /<phone_number_id>/messages`, body
  `{messaging_product: "whatsapp", to, type, text: {body}}`, autenticación
  por header `Authorization: Bearer <token>`) — necesita además el
  `phone_number_id` del canal (`Canal.telefono_id` en Core), no alcanza
  con el token solo."""
import httpx

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"
TIMEOUT_SEGUNDOS = 10.0


class EnvioFallido(Exception):
    def __init__(self, detalle: str):
        self.detalle = detalle
        super().__init__(detalle)


def _extraer_error(response: httpx.Response) -> str:
    data = response.json() if response.content else {}
    return (data.get("error") or {}).get("message") or f"La Graph API respondió {response.status_code}."


async def enviar_texto(*, api_key: str, destinatario_id: str, texto: str) -> dict:
    """Messenger / Instagram."""
    if not api_key:
        raise EnvioFallido("El canal no tiene api key cargada.")

    url = f"{GRAPH_API_BASE}/me/messages"
    payload = {"recipient": {"id": destinatario_id}, "message": {"text": texto}}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS) as client:
            response = await client.post(url, params={"access_token": api_key}, json=payload)
    except httpx.RequestError as exc:
        raise EnvioFallido(f"No se pudo conectar con la Graph API: {exc}") from exc

    if response.status_code != 200:
        raise EnvioFallido(_extraer_error(response))
    return response.json()


async def enviar_texto_por_canal(canal, destinatario_id: str, texto: str) -> dict:
    """Dispatcher genérico por `canal.tipo` (`schemas.CanalConfig`) — lo
    usan tanto `webhooks.py` (acciones que devuelve Core) como `messages.py`
    (`POST /messages/send`), para no repetir el `if tipo == "WHATSAPP"` en
    los dos lugares."""
    if canal.tipo == "WHATSAPP":
        return await enviar_texto_whatsapp(
            api_key=canal.api_key, telefono_id=canal.telefono_id, destinatario_id=destinatario_id, texto=texto,
        )
    return await enviar_texto(api_key=canal.api_key, destinatario_id=destinatario_id, texto=texto)


async def enviar_texto_whatsapp(*, api_key: str, telefono_id: str, destinatario_id: str, texto: str) -> dict:
    """WhatsApp Cloud API. `destinatario_id` es el número en formato E.164
    sin `+` (lo que Meta manda como `messages[].from` en el webhook)."""
    if not api_key:
        raise EnvioFallido("El canal no tiene api key (token) cargado.")
    if not telefono_id:
        raise EnvioFallido("El canal no tiene phone_number_id cargado.")

    url = f"{GRAPH_API_BASE}/{telefono_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": destinatario_id,
        "type": "text",
        "text": {"body": texto},
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SEGUNDOS) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise EnvioFallido(f"No se pudo conectar con la Cloud API: {exc}") from exc

    if response.status_code != 200:
        raise EnvioFallido(_extraer_error(response))
    return response.json()
