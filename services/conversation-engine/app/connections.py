"""Registro EN MEMORIA de qué WebSockets están conectados ahora mismo, por
organización — ver el docstring de `main.py` para por qué esto no está
persistido (`OperatorSession` de la sección 4.3 original de
docs/CONTEXTO_PROYECTO.md, a propósito no implementado como tabla).

Reenvía por ORGANIZACIÓN completa, no por equipo/operador puntual: es el
límite natural de scoping multi-tenant que ya usa el resto del proyecto, y
mantiene esto simple — el cliente ya recibe `team_id`/`operador_id` en el
payload del evento (`eventos.py`) para decidir del lado suyo si le importa
o no. Sólo sirve para UN proceso (`uvicorn` sin `--workers`, ver
Dockerfile) — escalar a más de una réplica necesita mover esto a algo
compartido entre procesos (Postgres LISTEN/NOTIFY, no Redis/Kafka —
restricción no negociable del proyecto), no antes de que haga falta."""
import asyncio

from fastapi import WebSocket


class GestorConexiones:
    def __init__(self) -> None:
        self._conexiones: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def conectar(self, organization_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._conexiones.setdefault(organization_id, set()).add(websocket)

    async def desconectar(self, organization_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            conexiones = self._conexiones.get(organization_id)
            if not conexiones:
                return
            conexiones.discard(websocket)
            if not conexiones:
                del self._conexiones[organization_id]

    async def transmitir(self, organization_id: int, payload: dict) -> int:
        """Devuelve a cuántas conexiones se le pudo mandar. Una conexión
        que ya se cayó (pero todavía no llegó su `disconnect`) se saca del
        registro acá mismo, en vez de esperar al `finally` del handler de
        `main.py` — evita que un evento futuro siga intentando mandarle
        algo a un socket muerto mientras tanto."""
        async with self._lock:
            conexiones = list(self._conexiones.get(organization_id, ()))
        entregados = 0
        for websocket in conexiones:
            try:
                await websocket.send_json(payload)
                entregados += 1
            except Exception:
                await self.desconectar(organization_id, websocket)
        return entregados

    def conectados(self, organization_id: int) -> int:
        return len(self._conexiones.get(organization_id, ()))


gestor = GestorConexiones()
