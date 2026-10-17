import logging
import httpx
from typing import List, Dict, Any
from app.config import settings

logger = logging.getLogger("webchat.core_client")

class CoreClient:
    """
    Cliente HTTP asíncrono para comunicarse con services/core (Django).
    Utiliza el encabezado 'Authorization: Service-Token <token>' para autenticarse,
    siguiendo exactamente el mismo estándar que channel-gateway y conversation-engine.
    """
    def __init__(self):
        self.base_url = settings.CORE_URL.rstrip("/")
        self.timeout = 10.0

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Service-Token {settings.CORE_SERVICE_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def enviar_mensaje_entrante(
        self,
        organization_id: int,
        visitor_id: str,
        texto: str
    ) -> List[Dict[str, Any]]:
        """
        Envía el mensaje del visitante a Core para que ejecute la lógica de negocio
        (menú, horario hábil, derivación).
        Endpoint en Core: POST /api/core/bot/mensaje-entrante/
        """
        url = f"{self.base_url}/api/core/bot/mensaje-entrante/"
        payload = {
            "organization_id": organization_id,
            "channel": "WEBCHAT",
            "contact_externo_id": visitor_id,
            "texto": texto,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=self._get_headers())
                
                if response.status_code == 200:
                    data = response.json()
                    acciones = data.get("acciones", [])
                    logger.info(f"[CoreClient] Core respondió con {len(acciones)} acciones para visitor {visitor_id}")
                    return acciones
                else:
                    logger.warning(
                        f"[CoreClient] Core devolvió status {response.status_code}: {response.text}"
                    )
                    return []
        except httpx.RequestError as exc:
            logger.error(f"[CoreClient] Error de conexión contra Core en {url}: {exc}")
            return []

    async def obtener_historial_sesion(
        self,
        organization_id: int,
        visitor_id: str
    ) -> List[Dict[str, Any]]:
        """
        Consulta a Core el historial reciente de mensajes de este visitante si el endpoint
        interno existe. Si aún no está implementado en Core (404), devuelve lista vacía limpiamente.
        """
        url = f"{self.base_url}/api/core/internal/mensajes/"
        params = {
            "organization_id": organization_id,
            "canal": "WEBCHAT",
            "contact_externo_id": visitor_id,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params, headers=self._get_headers())
                if response.status_code == 200:
                    data = response.json()
                    return data.get("mensajes", [])
                else:
                    logger.debug(f"[CoreClient] Endpoint de historial devolvió {response.status_code}")
                    return []
        except Exception as exc:
            logger.debug(f"[CoreClient] No se pudo consultar historial en Core: {exc}")
            return []

core_client = CoreClient()
