"""Cada familia de canal manda un formato de webhook distinto — dos formas,
no una:

- Messenger e Instagram: `entry[].messaging[]` (Instagram Direct reusa el
  contrato de Messenger Platform en vez de definir uno propio). El texto
  sale de `message.text` normalmente, o de `message.quick_reply.payload`
  cuando el contacto tocó un quick reply nativo (Instagram, ver
  `meta_client._enviar_quick_replies_messenger`) — ese `payload` es a
  propósito el mismo string ("1", "2"...) que un número tipeado a mano
  (mismo criterio que WhatsApp más abajo). Messenger manda siempre texto
  plano numerado (sin selector nativo — ver docstring de `meta_client`),
  así que ahí sólo entra la rama de `message.text`.
- WhatsApp (Cloud API): `entry[].changes[].value.messages[]`, con el
  remitente en `messages[].from` (el número, sin "+"). El texto sale de
  `messages[].text.body` para un mensaje de texto normal, o de
  `messages[].interactive.{list_reply,button_reply}.id` cuando el contacto
  tocó una fila/botón nativo en vez de escribir — ese `id` es a propósito
  el mismo string ("1", "2"...) que `conversations.menu_engine` ya sabe
  interpretar como número de opción (ver `meta_client.enviar_menu_por_canal`
  del lado del envío), así que no hace falta ninguna traducción especial
  acá, sólo tratarlo igual que si el contacto hubiera tipeado ese número.

En ambos casos se ignora todo lo que no sea texto o una respuesta
interactiva de un humano (recibos de entrega/lectura, eco de un mensaje
propio, `status` de WhatsApp) — ampliar acá cuando haga falta soportar
attachments/plantillas de verdad."""
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
            if not mensaje or mensaje.get("is_echo"):
                continue
            quick_reply = mensaje.get("quick_reply")
            if quick_reply and quick_reply.get("payload"):
                texto = quick_reply["payload"]
            elif "text" in mensaje:
                texto = mensaje["text"]
            else:
                continue
            remitente_id = (evento.get("sender") or {}).get("id")
            if not remitente_id:
                continue
            mensajes.append(MensajeEntrante(
                canal_tipo=canal_tipo,
                remitente_id=remitente_id,
                texto=texto,
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
                tipo_mensaje = mensaje.get("type")
                if tipo_mensaje == "text":
                    texto = (mensaje.get("text") or {}).get("body")
                elif tipo_mensaje == "interactive":
                    interactive = mensaje.get("interactive") or {}
                    reply = interactive.get("list_reply") or interactive.get("button_reply")
                    texto = reply.get("id") if reply else None
                else:
                    continue
                remitente_id = mensaje.get("from")
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
