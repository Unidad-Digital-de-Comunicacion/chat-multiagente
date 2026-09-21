"""Núcleo compartido de "cerrar una conversación" — usado tanto por
`ConversacionViewSet.cerrar` (manual, un operador la cierra a mano con
`mensaje_despedida`) como por el comando `cerrar_conversaciones_inactivas`
(automático, sin operador de por medio, con `mensaje_cierre_inactividad`).
Separado para no duplicar guardar+loguear+notificar en los dos lugares."""
from django.utils import timezone

from .channel_gateway_client import enviar_con_reintentos
from .conversation_engine_client import notificar_evento
from .models import Conversacion, ConversacionLog


def cerrar_conversacion(conversacion: Conversacion, *, mensaje: str) -> None:
    # El mensaje de cierre se manda ANTES de marcarla CERRADA (no después):
    # así, si alguien consulta el estado de la conversación justo en el
    # medio, nunca la ve ya cerrada sin que el mensaje de cierre haya
    # salido todavía.
    if mensaje:
        enviar_con_reintentos(conversacion, mensaje)
        ConversacionLog.objects.create(conversacion=conversacion, remitente=ConversacionLog.Remitente.SISTEMA, texto=mensaje)

    conversacion.estado = Conversacion.Estado.CERRADA
    conversacion.cerrada_at = timezone.now()
    conversacion.save(update_fields=["estado", "cerrada_at", "updated_at"])

    notificar_evento(
        tipo="conversacion_actualizada", organization_id=conversacion.organization_id,
        conversacion_id=conversacion.id, team_id=conversacion.team_id, operador_id=conversacion.operador_id,
    )
