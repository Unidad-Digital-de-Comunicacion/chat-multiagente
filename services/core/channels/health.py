"""Chequeo real de conexión contra el servidor remoto de cada canal — no es
un simulacro: para WhatsApp/Messenger/Instagram (todos sobre la Graph API de
Meta) pega de verdad a `GET /me` con la api key cargada para confirmar que
el servidor la acepta y está en línea. No valida que el token tenga los
permisos necesarios para mandar mensajes — eso es tarea del Channel Gateway
real (Fase 3, todavía no implementado), esto es sólo "¿el server contesta y
la key sirve?"."""
from django.utils import timezone

import requests

from .models import Canal

GRAPH_API_URL = "https://graph.facebook.com/v19.0/me"
TIMEOUT_SEGUNDOS = 6


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

    try:
        response = requests.get(
            GRAPH_API_URL, params={"access_token": canal.api_key}, timeout=TIMEOUT_SEGUNDOS,
        )
    except requests.RequestException as exc:
        return _guardar(canal, ok=False, detalle=f"No se pudo conectar: {exc}"[:255])

    try:
        data = response.json()
    except ValueError:
        data = {}

    if response.status_code == 200 and "id" in data:
        nombre = data.get("name") or data.get("id")
        return _guardar(canal, ok=True, detalle=f"Conectado — {nombre}"[:255])

    mensaje = (data.get("error") or {}).get("message") or f"El servidor respondió {response.status_code}."
    return _guardar(canal, ok=False, detalle=mensaje[:255])


def _guardar(canal: Canal, *, ok, detalle: str) -> Canal:
    canal.ultimo_chequeo_at = timezone.now()
    canal.ultimo_chequeo_ok = ok
    canal.ultimo_chequeo_detalle = detalle
    canal.save(update_fields=["ultimo_chequeo_at", "ultimo_chequeo_ok", "ultimo_chequeo_detalle"])
    return canal
