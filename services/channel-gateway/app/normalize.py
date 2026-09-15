"""Cada familia de canal manda un formato de webhook distinto — dos formas,
no una:

- Messenger e Instagram: `entry[].messaging[]` (Instagram Direct reusa el
  contrato de Messenger Platform en vez de definir uno propio).
- WhatsApp (Cloud API): `entry[].changes[].value.messages[]`, con el
  remitente en `messages[].from` (el número, sin "+") y el texto en
  `messages[].text.body`.

En ambos casos se ignora todo lo que no sea un mensaje de texto de un
humano (recibos de entrega/lectura, eco de un mensaje propio, postbacks de
botones, `status` de WhatsApp) — ampliar acá cuando haga falta soportar
attachments/botones/plantillas de verdad."""
from .schemas import MensajeEntrante


def normalizar_mensajes(canal_tipo: str, payload: dict) -> list[MensajeEntrante]:
    if canal_tipo == "whatsapp":
        return _normalizar_whatsapp(canal_tipo, payload)
    return _normalizar_messenger_instagram(canal_tipo, payload)


def _normalizar_messenger_instagram(canal_tipo: str, payload: dict) -> list[MensajeEntrante]:
    mensajes = []
    for entry in payload.get("entry", []):
        for evento in entry.get("messaging", []):
            mensaje = evento.get("message")
            if not mensaje or mensaje.get("is_echo") or "text" not in mensaje:
                continue
            remitente_id = (evento.get("sender") or {}).get("id")
            if not remitente_id:
                continue
            mensajes.append(MensajeEntrante(
                canal_tipo=canal_tipo,
                remitente_id=remitente_id,
                texto=mensaje["text"],
                timestamp_ms=evento.get("timestamp", 0),
            ))
    return mensajes


def _normalizar_whatsapp(canal_tipo: str, payload: dict) -> list[MensajeEntrante]:
    mensajes = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "messages":
                continue
            valor = change.get("value") or {}
            for mensaje in valor.get("messages", []):
                if mensaje.get("type") != "text":
                    continue
                remitente_id = mensaje.get("from")
                texto = (mensaje.get("text") or {}).get("body")
                if not remitente_id or not texto:
                    continue
                timestamp = mensaje.get("timestamp")
                mensajes.append(MensajeEntrante(
                    canal_tipo=canal_tipo,
                    remitente_id=remitente_id,
                    texto=texto,
                    # WhatsApp manda el timestamp en segundos (string), no ms.
                    timestamp_ms=int(timestamp) * 1000 if timestamp else 0,
                ))
    return mensajes
