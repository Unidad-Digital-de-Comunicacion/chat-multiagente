"""Chequeo real de conexión contra el servidor remoto de cada canal — no es
un simulacro: para WhatsApp/Messenger/Instagram (todos sobre la Graph API de
Meta) confirma que el servidor acepta la `api_key` cargada y está en línea.

**WhatsApp** usa un nodo y una autenticación distintos de Messenger/
Instagram (mismo criterio que el envío real de mensajes,
`channel-gateway/app/meta_client.py` — ver su docstring): un token de
System User de la Cloud API casi nunca puede resolver `/me` (Meta responde
`"Unsupported get request..."`/permission error) aunque ese mismo token
mande mensajes perfectamente por `/<phone_number_id>/messages` con
`Authorization: Bearer`. El nodo real para verificar es el propio
`phone_number_id` (`Canal.telefono_id`), con el token en el header
`Authorization: Bearer`, igual que el envío real. Confirmado en producción
(2026-09-16): esto arregló un canal 100% funcional que el chequeo viejo
(`/me` + query param) marcaba "sin conexión".

**Messenger/Instagram**: un Page Access Token con sólo el permiso
`pages_messaging` (lo mínimo que hace falta para mandar mensajes, que es
lo único que de verdad importa acá) NO puede leer `/me` — Meta devuelve
`(#100) ... requires the 'pages_read_engagement' permission ...` aunque el
token ande perfecto para enviar (mismo caso que WhatsApp: confirmado en
producción, un canal funcional marcado "sin conexión" por pedirle a `/me`
un permiso de lectura que el token de mensajería no tiene por qué tener).
La forma correcta de validar un token SIN depender de qué permisos tenga
es `/debug_token`, autenticado con las credenciales de la APP
(`META_APP_ID`/`META_APP_SECRET`, ya usadas en `embedded_signup.py`), no
con el token del canal — es el mecanismo que la propia Graph API
documenta para esto (`is_valid`/`scopes`/`expires_at`)."""
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.utils import timezone

import requests

from .models import Canal

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"
TIMEOUT_SEGUNDOS = 10


def verificar_conexion(canal: Canal) -> Canal:
    if not canal.api_key:
        return _guardar(canal, ok=False, detalle="No hay api key cargada.")

    if canal.tipo not in Canal.TIPOS_CON_WEBHOOK_META:
        # Webchat no tiene un servidor de terceros que consultar — el
        # servidor "remoto" sería el propio Webchat Service (Fase 9,
        # todavía no construido), así que no hay nada real que chequear acá.
        return _guardar(
            canal, ok=None,
            detalle="Webchat no tiene un servidor externo que verificar todavía (Webchat Service, Fase 9).",
        )

    if canal.tipo == Canal.Tipo.WHATSAPP:
        return _verificar_whatsapp(canal)
    return _verificar_messenger_o_instagram(canal)


def _verificar_whatsapp(canal: Canal) -> Canal:
    if not canal.telefono_id:
        return _guardar(canal, ok=False, detalle="Falta el Phone Number ID (telefono_id).")

    url = f"{GRAPH_API_BASE}/{canal.telefono_id}"
    try:
        response = requests.get(
            url, params={"fields": "verified_name,display_phone_number,quality_rating"},
            headers={"Authorization": f"Bearer {canal.api_key}"}, timeout=TIMEOUT_SEGUNDOS,
        )
    except requests.RequestException as exc:
        return _guardar(canal, ok=False, detalle=f"No se pudo conectar: {exc}")

    data = _parsear(response)
    if response.status_code == 200 and "id" in data:
        nombre = data.get("verified_name") or data.get("display_phone_number") or data.get("id")
        return _guardar(canal, ok=True, detalle=f"Conectado — {nombre}")
    return _guardar(canal, ok=False, detalle=_mensaje_error(response, data))


def _verificar_messenger_o_instagram(canal: Canal) -> Canal:
    # Instagram puede vivir bajo una app de Meta distinta a la de Messenger/
    # WhatsApp (`config.settings.META_APP_ID_INSTAGRAM`, ver su comentario) —
    # `/debug_token` tiene que autenticarse con las credenciales de la app
    # que realmente emitió/gestiona ese token, no con las de la otra.
    if canal.tipo == Canal.Tipo.INSTAGRAM:
        app_id, app_secret = settings.META_APP_ID_INSTAGRAM, settings.META_APP_SECRET_INSTAGRAM
    else:
        app_id, app_secret = settings.META_APP_ID, settings.META_APP_SECRET
    if not app_id or not app_secret:
        return _guardar(canal, ok=False, detalle="Falta configurar META_APP_ID/META_APP_SECRET en el servidor.")

    url = f"{GRAPH_API_BASE}/debug_token"
    try:
        response = requests.get(
            url,
            params={"input_token": canal.api_key, "access_token": f"{app_id}|{app_secret}"},
            timeout=TIMEOUT_SEGUNDOS,
        )
    except requests.RequestException as exc:
        return _guardar(canal, ok=False, detalle=f"No se pudo conectar: {exc}")

    payload = _parsear(response)
    data = payload.get("data") or {}
    if response.status_code == 200 and data.get("is_valid"):
        return _guardar(canal, ok=True, detalle=f"Token válido — {_formatear_vencimiento(data.get('expires_at'))}")
    if response.status_code == 200 and "data" in payload:
        # `/debug_token` respondió 200 igual (así funciona esta API: el
        # error real de UN token va adentro de `data`, no en el nivel de
        # arriba como el resto de la Graph API) — token vencido/revocado.
        mensaje = (data.get("error") or {}).get("message") or "El token ya no es válido."
        return _guardar(canal, ok=False, detalle=mensaje)
    return _guardar(canal, ok=False, detalle=_mensaje_error(response, payload))


def _formatear_vencimiento(expires_at) -> str:
    if not expires_at:
        # `0` (o ausente) es el valor real que devuelve Meta para un token
        # de larga duración sin vencimiento — no es un dato faltante.
        return "no vence"
    return f"vence {datetime.fromtimestamp(expires_at, tz=dt_timezone.utc).strftime('%d/%m/%Y')}"


def _parsear(response: requests.Response) -> dict:
    try:
        return response.json()
    except ValueError:
        return {}


def _mensaje_error(response: requests.Response, data: dict) -> str:
    """Suma `code`/`error_subcode` de Meta al mensaje (no sólo `message`) —
    son lo que de verdad distingue "token vencido" de "el token no tiene
    permiso para este nodo" al mirar el detalle desde el Admin Panel, sin
    tener que ir a buscar los logs."""
    error = data.get("error") or {}
    mensaje = error.get("message") or f"El servidor respondió {response.status_code}."
    codigo, subcodigo = error.get("code"), error.get("error_subcode")
    if codigo is not None:
        mensaje += f" (code={codigo}, subcode={subcodigo})" if subcodigo is not None else f" (code={codigo})"
    return mensaje


def _guardar(canal: Canal, *, ok, detalle: str) -> Canal:
    canal.ultimo_chequeo_at = timezone.now()
    canal.ultimo_chequeo_ok = ok
    canal.ultimo_chequeo_detalle = (detalle or "")[:255]
    canal.save(update_fields=["ultimo_chequeo_at", "ultimo_chequeo_ok", "ultimo_chequeo_detalle"])
    return canal
