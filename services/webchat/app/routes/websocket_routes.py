import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.connection_manager import manager

logger = logging.getLogger("webchat.websocket_routes")

router = APIRouter(tags=["WebSocket"])

@router.websocket("/ws/visitante/{visitor_id}")
async def websocket_visitante(websocket: WebSocket, visitor_id: str):
    """
    Canal de bajada en tiempo real hacia el widget del visitante.
    Se mantiene abierto mientras el visitante navegue por la página.
    """
    await manager.connect(visitor_id, websocket)
    
    # Notificar al widget que la conexión está activa
    await manager.send_to_visitor(visitor_id, {
        "tipo": "conexion_establecida",
        "visitor_id": visitor_id
    })

    try:
        while True:
            # Escucha eventos o pings del cliente para mantener el socket activo
            data = await websocket.receive_text()
            # Si el cliente manda un ping, respondemos pong
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(visitor_id, websocket)
    except Exception as e:
        logger.error(f"[WS] Error inesperado en socket de visitante {visitor_id}: {e}")
        manager.disconnect(visitor_id, websocket)
