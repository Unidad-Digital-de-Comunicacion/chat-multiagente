"""Cliente HTTP para que Core le pida a Channel Gateway que mande un mensaje
saliente de verdad (`POST /messages/send`) — la dirección INVERSA del resto
de la integración (ahí Channel Gateway es el que le pide cosas a Core). Usa
el mismo secreto compartido (`ServiceToken` del servicio `CHANNEL_GATEWAY`,
`platform_admin.service_auth`) que ya existe para la otra dirección — no
hace falta un segundo secreto sólo para esto."""
import requests

from django.conf import settings

from channels.models import Canal
from platform_admin.models import ServiceToken

TIMEOUT_SEGUNDOS = 10


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
