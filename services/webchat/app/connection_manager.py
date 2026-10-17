import json
import logging
from typing import Dict
from fastapi import WebSocket

logger = logging.getLogger("webchat.connection_manager")

class ConnectionManager:
    """
    Administra las conexiones WebSocket activas de los visitantes anónimos.
    Mapea visitor_id -> WebSocket para entregar mensajes en tiempo real
    (respuestas de Core y mensajes de operadores humanos).
    """
    def __init__(self):
        # Mapeo en memoria: visitor_id (str) -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, visitor_id: str, websocket: WebSocket):
        await websocket.accept()
        # Si ya había una conexión previa para este visitante (ej. recarga rápida o pestaña duplicada), la cerramos limpiamente
        if visitor_id in self.active_connections:
            old_ws = self.active_connections[visitor_id]
            try:
                await old_ws.close(code=1000, reason="Nueva sesión conectada")
            except Exception:
                pass
        self.active_connections[visitor_id] = websocket
        logger.info(f"[WS] Visitante conectado: {visitor_id} (Total activos: {len(self.active_connections)})")

    def disconnect(self, visitor_id: str, websocket: WebSocket):
        if visitor_id in self.active_connections and self.active_connections[visitor_id] == websocket:
            del self.active_connections[visitor_id]
            logger.info(f"[WS] Visitante desconectado: {visitor_id} (Total activos: {len(self.active_connections)})")

    async def send_to_visitor(self, visitor_id: str, payload: dict) -> bool:
        """
        Envía un mensaje en formato JSON al WebSocket de un visitante.
        Retorna True si el mensaje fue entregado, False si el visitante no está conectado.
        """
        websocket = self.active_connections.get(visitor_id)
        if not websocket:
            logger.warning(f"[WS] No se pudo entregar mensaje: visitante {visitor_id} no está conectado")
            return False

        try:
            await websocket.send_text(json.dumps(payload, ensure_ascii=False))
            return True
        except Exception as e:
            logger.error(f"[WS] Error enviando mensaje a visitante {visitor_id}: {e}")
            if visitor_id in self.active_connections:
                del self.active_connections[visitor_id]
            return False

    def is_connected(self, visitor_id: str) -> bool:
        return visitor_id in self.active_connections

manager = ConnectionManager()
