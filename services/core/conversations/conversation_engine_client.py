"""Avisa a Conversation Engine (Fase 4 — entrega en tiempo real por
WebSocket a los clientes operador, `services/conversation-engine`) cada vez
que pasa algo relevante para la bandeja: mismo patrón/secreto compartido
(`ServiceToken` del servicio `CONVERSATION_ENGINE`, `platform_admin.
service_auth`) que `channel_gateway_client.enviar_mensaje_saliente` usa
para la dirección Core -> Channel Gateway.

A propósito "mejor esfuerzo": si Conversation Engine está caído o no
configurado, la conversación igual se guardó bien en Core — el cliente
operador se entera igual en el próximo polling (ver §7 de
docs/operators-desk-api-contract.md). Nunca debe romper el flujo principal
por esto, por eso todas las excepciones de red quedan atrapadas acá
adentro, igual que en `channel_gateway_client`."""
import requests

from django.conf import settings

from platform_admin.models import ServiceToken

TIMEOUT_SEGUNDOS = 3


def notificar_evento(
    *, tipo: str, organization_id: int, conversacion_id: int, team_id: int | None = None,
    operador_id: int | None = None,
) -> None:
    token = ServiceToken.objects.filter(
        servicio=ServiceToken.Servicio.CONVERSATION_ENGINE, activo=True,
    ).exclude(token="").values_list("token", flat=True).first()
    if not token:
        return

    try:
        requests.post(
            f"{settings.CONVERSATION_ENGINE_INTERNAL_URL}/internal/eventos/",
            json={
                "tipo": tipo, "organization_id": organization_id, "conversacion_id": conversacion_id,
                "team_id": team_id, "operador_id": operador_id,
            },
            headers={"Authorization": f"Service-Token {token}"},
            timeout=TIMEOUT_SEGUNDOS,
        )
    except requests.RequestException:
        pass
