"""Cliente HTTP para que Core le pida a Channel Gateway que mande un mensaje
saliente de verdad (`POST /messages/send`) — la dirección INVERSA del resto
de la integración (ahí Channel Gateway es el que le pide cosas a Core). Usa
el mismo secreto compartido (`ServiceToken` del servicio `CHANNEL_GATEWAY`,
`platform_admin.service_auth`) que ya existe para la otra dirección — no
hace falta un segundo secreto sólo para esto.

`enviar_con_reintentos` es la función que hay que llamar desde afuera (no
`enviar_mensaje_saliente` directo) — envuelve el mismo envío con hasta 3
intentos y backoff corto, pensada para el caso real confirmado en
producción (2026-09-18/19): un bache momentáneo de conectividad interna
entre Channel Gateway y Core (`CoreNoDisponible`, ver `channel-gateway/app/
core_client.py`) que dura de menos de un segundo a un par de segundos y se
resuelve solo en el intento siguiente."""
import time

import requests

from django.conf import settings

from channels.models import Canal
from platform_admin.models import ServiceToken

from .models import ConversacionLog, EnvioSaliente

TIMEOUT_SEGUNDOS = 10

MAX_INTENTOS = 3
# Entre intento y el siguiente, no antes del primero — 2 pausas para 3
# intentos. Corto a propósito: Core corre acá con UN solo worker
# sincrónico (`docker-compose.override.yml`), así que cada segundo de
# backoff bloquea ese worker entero para cualquier otro request mientras
# tanto — no es gratis, sólo vale la pena porque las fallas reales
# observadas duraron bien poco.
BACKOFF_SEGUNDOS = [1, 2]

MENSAJE_NO_ENVIADO = "No se pudo enviar este mensaje."


def enviar_con_reintentos(conversacion, texto: str) -> bool:
    envio = EnvioSaliente.objects.create(conversacion=conversacion, texto=texto)
    for intento in range(1, MAX_INTENTOS + 1):
        exito = enviar_mensaje_saliente(conversacion, texto)
        envio.intentos = intento
        if exito:
            envio.estado = EnvioSaliente.Estado.ENVIADO
            envio.save(update_fields=["intentos", "estado", "actualizado_at"])
            return True
        if intento < MAX_INTENTOS:
            time.sleep(BACKOFF_SEGUNDOS[intento - 1])

    envio.estado = EnvioSaliente.Estado.FALLIDO
    envio.ultimo_error = f"No se pudo entregar después de {MAX_INTENTOS} intentos."
    envio.save(update_fields=["intentos", "estado", "ultimo_error", "actualizado_at"])
    # Aviso visible para el operador en el propio hilo — sin esto, el
    # mensaje quedaba "enviado" desde su punto de vista aunque el contacto
    # nunca lo hubiera recibido (el bug real que motivó todo esto).
    ConversacionLog.objects.create(
        conversacion=conversacion, remitente=ConversacionLog.Remitente.SISTEMA, texto=MENSAJE_NO_ENVIADO,
    )
    return False


def enviar_mensaje_saliente(conversacion, texto: str) -> bool:
    try:
        canal = Canal.objects.get(organization_id=conversacion.organization_id, tipo=conversacion.canal)
    except Canal.DoesNotExist:
        return False

    token = ServiceToken.objects.filter(
        servicio=ServiceToken.Servicio.CHANNEL_GATEWAY, activo=True,
    ).exclude(token="").values_list("token", flat=True).first()
    if not token:
        return False

    try:
        response = requests.post(
            f"{settings.CHANNEL_GATEWAY_INTERNAL_URL}/messages/send",
            json={
                "canal_uuid": str(canal.uuid),
                "destinatario_id": conversacion.contact.identificador_externo,
                "texto": texto,
            },
            headers={"Authorization": f"Service-Token {token}"},
            timeout=TIMEOUT_SEGUNDOS,
        )
    except requests.RequestException:
        return False
    return response.status_code == 200
