"""Envío de mensajes salientes vía la Graph API de Meta — dos formas
distintas, no intercambiables:

- Messenger/Instagram comparten la misma "Send API" (`POST /me/messages`
  con `{recipient: {id}, message: {text}}`, autenticación por query param
  `access_token`).
- WhatsApp usa la Cloud API (`POST /<phone_number_id>/messages`, body
  `{messaging_product: "whatsapp", to, type, ...}`, autenticación por
  header `Authorization: Bearer <token>`) — necesita además el
  `phone_number_id` del canal (`Canal.telefono_id` en Core), no alcanza
  con el token solo.

`enviar_menu_por_canal` es la traducción de la sección 4.1.1 de docs/
CONTEXTO_PROYECTO.md: WhatsApp tiene widgets nativos de selección
(`interactive.type=list` para 4-10 opciones, `interactive.type=button`
para 1-3) — ahí sí se usan. Para Messenger se probaron tres alternativas
nativas (`message.quick_replies`, Button Template repetido en varios
mensajes, Generic Template en carrusel) y ninguna funcionó bien en la
práctica, así que **Messenger manda siempre el texto plano numerado**
(mismo fallback universal que Core ya arma) y el contacto responde
escribiendo el número — sin selector táctil. **Instagram usa exactamente
la misma configuración que Messenger** (2026-09-20, pedido explícito):
antes probaba `message.quick_replies`, pero en producción el menú no le
llegaba al contacto — se unificó para que ambos canales se comporten
igual, sin selector táctil en ninguno de los dos, en vez de seguir
depurando la rama nativa de Instagram por separado.

Cada función recibe el `httpx.AsyncClient` compartido de la app como
parámetro explícito (ver `http_client.py`/`main.py`) en vez de instanciar
uno propio por llamada — mismo criterio que `core_client.py`."""
import httpx

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"

# Límites reales de la Cloud API de WhatsApp (sección 4.1.1).
WHATSAPP_BOTONES_MAX = 3
WHATSAPP_LISTA_MAX = 10
WHATSAPP_TITULO_BOTON_MAX = 20
WHATSAPP_TITULO_FILA_MAX = 24

class EnvioFallido(Exception):
    def __init__(self, detalle: str):
        self.detalle = detalle
        super().__init__(detalle)


def _extraer_error(response: httpx.Response) -> str:
    data = response.json() if response.content else {}
    return (data.get("error") or {}).get("message") or f"La Graph API respondió {response.status_code}."


async def enviar_texto(client: httpx.AsyncClient, *, api_key: str, destinatario_id: str, texto: str) -> dict:
    """Messenger / Instagram."""
    if not api_key:
        raise EnvioFallido("El canal no tiene api key cargada.")

    url = f"{GRAPH_API_BASE}/me/messages"
    payload = {"recipient": {"id": destinatario_id}, "message": {"text": texto}}
    try:
        response = await client.post(url, params={"access_token": api_key}, json=payload)
    except httpx.RequestError as exc:
        raise EnvioFallido(f"No se pudo conectar con la Graph API: {exc}") from exc

    if response.status_code != 200:
        raise EnvioFallido(_extraer_error(response))
    return response.json()


async def enviar_texto_por_canal(client: httpx.AsyncClient, canal, destinatario_id: str, texto: str) -> dict:
    """Dispatcher genérico por `canal.tipo` (`schemas.CanalConfig`) — lo
    usan tanto `webhooks.py` (acciones que devuelve Core) como `messages.py`
    (`POST /messages/send`), para no repetir el `if tipo == "WHATSAPP"` en
    los dos lugares."""
    if canal.tipo == "WHATSAPP":
        return await enviar_texto_whatsapp(
            client, api_key=canal.api_key, telefono_id=canal.telefono_id, destinatario_id=destinatario_id, texto=texto,
        )
    return await enviar_texto(client, api_key=canal.api_key, destinatario_id=destinatario_id, texto=texto)


async def enviar_menu_por_canal(
    client: httpx.AsyncClient, canal, destinatario_id: str, texto: str, encabezado: str, opciones: list[dict],
) -> dict:
    """`texto` = fallback completo con numeración — lo único que manda el
    texto plano, y lo que WhatsApp muestra COMO CUERPO además de su widget
    táctil (pedido explícito para ese canal). `encabezado` queda sin usar
    fuera de WhatsApp: Messenger e Instagram (misma configuración los dos,
    ver docstring del módulo) caen siempre al texto plano de `texto`.
    `opciones` = `[{id, titulo}]`."""
    if canal.tipo == "WHATSAPP":
        cantidad = len(opciones)
        if 1 <= cantidad <= WHATSAPP_BOTONES_MAX:
            return await _enviar_botones_whatsapp(client, canal, destinatario_id, texto, opciones)
        if WHATSAPP_BOTONES_MAX < cantidad <= WHATSAPP_LISTA_MAX:
            return await _enviar_lista_whatsapp(client, canal, destinatario_id, texto, opciones)
    # Fuera de rango, sin opciones, Messenger/Instagram, o WhatsApp mal
    # configurado -> texto plano numerado.
    return await enviar_texto_por_canal(client, canal, destinatario_id, texto)


async def _post_whatsapp(client: httpx.AsyncClient, api_key: str, telefono_id: str, payload: dict) -> dict:
    if not api_key:
        raise EnvioFallido("El canal no tiene api key (token) cargado.")
    if not telefono_id:
        raise EnvioFallido("El canal no tiene phone_number_id cargado.")

    url = f"{GRAPH_API_BASE}/{telefono_id}/messages"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        response = await client.post(url, headers=headers, json=payload)
    except httpx.RequestError as exc:
        raise EnvioFallido(f"No se pudo conectar con la Cloud API: {exc}") from exc

    if response.status_code != 200:
        raise EnvioFallido(_extraer_error(response))
    return response.json()


async def enviar_texto_whatsapp(
    client: httpx.AsyncClient, *, api_key: str, telefono_id: str, destinatario_id: str, texto: str,
) -> dict:
    """WhatsApp Cloud API. `destinatario_id` es el número en formato E.164
    sin `+` (lo que Meta manda como `messages[].from` en el webhook)."""
    payload = {
        "messaging_product": "whatsapp",
        "to": destinatario_id,
        "type": "text",
        "text": {"body": texto},
    }
    return await _post_whatsapp(client, api_key, telefono_id, payload)


async def _enviar_botones_whatsapp(
    client: httpx.AsyncClient, canal, destinatario_id: str, texto: str, opciones: list[dict],
) -> dict:
    """1 a 3 opciones -> `interactive.type=button` (título de cada botón,
    máx. 20 caracteres). `texto` (encabezado + listado numerado) va de
    cuerpo del mensaje — se ve el texto completo Y los botones táctiles
    debajo, no sólo los botones."""
    payload = {
        "messaging_product": "whatsapp",
        "to": destinatario_id,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "body": {"text": texto or "Elegí una opción:"},
            "action": {"buttons": [
                {"type": "reply", "reply": {"id": o["id"], "title": o["titulo"][:WHATSAPP_TITULO_BOTON_MAX]}}
                for o in opciones
            ]},
        },
    }
    return await _post_whatsapp(client, canal.api_key, canal.telefono_id, payload)


async def _enviar_lista_whatsapp(
    client: httpx.AsyncClient, canal, destinatario_id: str, texto: str, opciones: list[dict],
) -> dict:
    """4 a 10 opciones -> `interactive.type=list` (título de cada fila,
    máx. 24 caracteres). Mismo criterio que los botones: `texto` (con el
    listado numerado) va de cuerpo, visible aparte del botón "Ver opciones"
    que abre el selector táctil."""
    payload = {
        "messaging_product": "whatsapp",
        "to": destinatario_id,
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": texto or "Elegí una opción:"},
            "action": {
                "button": "Seleccione opción",
                "sections": [{"rows": [
                    {"id": o["id"], "title": o["titulo"][:WHATSAPP_TITULO_FILA_MAX]}
                    for o in opciones
                ]}],
            },
        },
    }
    return await _post_whatsapp(client, canal.api_key, canal.telefono_id, payload)
