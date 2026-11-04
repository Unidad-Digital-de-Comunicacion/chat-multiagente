"""Cliente HTTP para que Core le pida al servicio Webchat que entregue un
mensaje saliente al visitante correspondiente (`POST /messages/send`) —
misma dirección inversa y mismo patrón de secreto-por-servicio que
`channel_gateway_client.py`, pero con su propio `ServiceToken` (`WEBCHAT`)
y su propia URL interna: Webchat no pasa por Meta, así que no tiene
`canal_uuid`/`destinatario_id` — el identificador real es el `visitor_id`
que ya es `Contact.identificador_externo` del lado de Core."""
import requests

from django.conf import settings

from common.observabilidad import headers_request_id
from platform_admin.models import ServiceToken

TIMEOUT_SEGUNDOS = 10


def enviar_mensaje_saliente(conversacion, texto: str) -> bool:
    token = ServiceToken.objects.filter(
        servicio=ServiceToken.Servicio.WEBCHAT, activo=True,
    ).exclude(token="").values_list("token", flat=True).first()
    if not token:
        return False

    try:
        response = requests.post(
            f"{settings.WEBCHAT_INTERNAL_URL}/messages/send",
            json={"visitor_id": conversacion.contact.identificador_externo, "texto": texto},
            headers={"Authorization": f"Service-Token {token}", **headers_request_id()},
            timeout=TIMEOUT_SEGUNDOS,
        )
    except requests.RequestException:
        return False
    return response.status_code == 200
