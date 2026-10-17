import logging
from fastapi import APIRouter, Depends
from app.schemas import (
    MensajeVisitanteRequest,
    MensajeVisitanteResponse,
    MensajeOperadorRequest,
    MensajeOperadorResponse,
)
from app.internal_auth import verify_service_token
from app.core_client import core_client
from app.connection_manager import manager

logger = logging.getLogger("webchat.message_routes")

router = APIRouter(tags=["Mensajes"])

@router.post("/mensajes/", response_model=MensajeVisitanteResponse)
async def recibir_mensaje_visitante(payload: MensajeVisitanteRequest):
    """
    Endpoint consumido por el widget del visitante (REST).
    1. Recibe el texto ingresado por el visitante.
    2. Lo delega a Core (POST /api/core/bot/mensaje-entrante/).
    3. Core ejecuta la lógica y devuelve una lista de 'acciones'.
    4. Las acciones se empujan en tiempo real por el WebSocket del visitante.
    """
    # Notificar a Core
    acciones = await core_client.enviar_mensaje_entrante(
        organization_id=payload.organization_id,
        visitor_id=payload.visitor_id,
        texto=payload.texto
    )

    # Empujar las acciones al WebSocket del visitante
    for accion in acciones:
        tipo = accion.get("tipo")
        if tipo == "enviar_texto":
            await manager.send_to_visitor(
                payload.visitor_id,
                {"tipo": "mensaje_bot", "texto": accion.get("texto", "")}
            )
        elif tipo == "mostrar_menu":
            await manager.send_to_visitor(
                payload.visitor_id,
                {
                    "tipo": "menu",
                    "texto": accion.get("texto", ""),
                    "encabezado": accion.get("encabezado", "Menú de opciones"),
                    "opciones": accion.get("opciones", [])
                }
            )
        else:
            # Reenvío genérico de cualquier otra acción futura de Core
            await manager.send_to_visitor(payload.visitor_id, accion)

    return MensajeVisitanteResponse(status="ok", acciones=acciones)


@router.post("/messages/send", response_model=MensajeOperadorResponse)
async def recibir_mensaje_operador(
    payload: MensajeOperadorRequest,
    _: bool = Depends(verify_service_token)
):
    """
    Endpoint consumido por Core cuando un operador humano responde desde el Operators Desk.
    Protegido con Authorization: Service-Token.
    Empuja el texto directamente al WebSocket del visitante correspondiente.
    """
    delivered = await manager.send_to_visitor(
        visitor_id=payload.visitor_id,
        payload={
            "tipo": "mensaje_operador",
            "texto": payload.texto
        }
    )

    if delivered:
        logger.info(f"[Core -> Webchat] Mensaje de operador entregado a {payload.visitor_id}")
    else:
        logger.warning(f"[Core -> Webchat] Visitante {payload.visitor_id} no está conectado actualmente")

    return MensajeOperadorResponse(
        status="delivered" if delivered else "queued",
        delivered=delivered
    )
