"""Conversation Engine — Fase 4 de docs/CONTEXTO_PROYECTO.md: entrega en
tiempo real, por WebSocket, de eventos que ya decidió y guardó Core (nunca
al revés — este servicio no tiene ninguna fuente de verdad de negocio
propia, sección 2.1 "Core decide, todo lo demás ejecuta"). Core avisa acá
(`POST /internal/eventos/`, protegido con el mismo esquema `Service-Token`
que el resto de los servicios internos, ver `internal_auth.py`) cada vez
que pasa algo relevante para un operador conectado
(`conversations.conversation_engine_client.notificar_evento` del lado de
Core), y este servicio lo reenvía por WebSocket a quien tenga la app
abierta (`connections.py`).

Recorte deliberado respecto de la sección 4.3/Fase 4 originales: NO hay
`OperatorSession`/`AsignacionChat` persistidos en base — la asignación
real (`team`/`operador`/lock de 2 minutos) sigue viviendo enteramente en
`Conversacion` de Core (`conversations.views.ConversacionViewSet`, ya
implementado ahí), así que duplicarla acá sería una segunda fuente de
verdad sin necesidad real. Lo único que vive en este proceso es qué
WebSockets están conectados AHORA MISMO (en memoria, `connections.py`) —
no sobrevive un restart ni escala a más de un worker todavía; ver el
docstring de `connections.py` para cuándo (y cómo) resolver eso.

El payload de cada evento es a propósito mínimo (`eventos.py`) — nunca el
contenido real de un mensaje/observación, el cliente que lo recibe
refresca por REST contra Core lo que le importa. Si esta conexión no está
disponible (servicio caído, sin token configurado, cliente sin
conexión), el cliente igual se entera por polling en su próximo refresco
— ver §7 de docs/operators-desk-api-contract.md."""
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from .auth import operador_autenticado, verificar_token
from .connections import gestor
from .eventos import EventoConversacion
from .http_client import get_http_client
from .internal_auth import requerir_servicio_interno
from .observabilidad import MiddlewareRequestId, configurar_logging, propagar_request_id

configurar_logging("conversation-engine")


class HealthResponse(BaseModel):
    status: str


class EventoRecibidoResponse(BaseModel):
    entregados: int


class ConexionesActivasResponse(BaseModel):
    conectados: int

# Códigos de cierre de WebSocket en el rango privado (4000-4999, RFC 6455)
# — 4401 para que el cliente pueda distinguir "token inválido/vencido" de
# un corte de red común y, si tiene el refresh token, reintente con un
# access token nuevo antes de resignarse a mostrar un error.
WS_CODIGO_NO_AUTORIZADO = 4401


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with httpx.AsyncClient(timeout=10.0, event_hooks={"request": [propagar_request_id]}) as client:
        app.state.http_client = client
        yield


# Swagger (`/docs`) y Redoc (`/redoc`) vienen solos con FastAPI, sin nada
# que armar a mano — a diferencia de Core (drf-spectacular). El único
# endpoint que de verdad importa acá (`WS /ws/operador/{token}`) NO va a
# aparecer en ninguno de los dos: OpenAPI no tiene forma de documentar un
# WebSocket, es una limitación del formato, no algo que falte configurar.
# `description` de acá abajo es lo primero que ve alguien que entra a
# `/docs` — deja eso explícito y linkea al contrato real.
DESCRIPCION = (
    "Entrega en tiempo real (Fase 4) para clientes operador — ver "
    "docs/operators-desk-api-contract.md §7 en el repo para el contrato "
    "completo, INCLUIDO `WS /ws/operador/{token}`, que no aparece acá "
    "abajo porque OpenAPI no documenta WebSockets."
)

app = FastAPI(title="Conversation Engine Service", description=DESCRIPCION, lifespan=lifespan)
app.add_middleware(MiddlewareRequestId)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.websocket("/ws/operador/{token}")
async def ws_operador(websocket: WebSocket, token: str, client: httpx.AsyncClient = Depends(get_http_client)) -> None:
    try:
        claims = await verificar_token(token, client)
    except Exception:
        # Cubre tanto un JWT inválido/vencido (`jwt.InvalidTokenError`)
        # como no poder llegar a buscar el JWKS de Core — en los dos casos
        # la conexión no se puede autenticar, así que se cierra igual.
        await websocket.close(code=WS_CODIGO_NO_AUTORIZADO)
        return

    await gestor.conectar(claims.organization_id, websocket)
    try:
        while True:
            # Este servicio no espera nada del cliente hoy (es sólo
            # entrega, no un chat en sí) — el `receive` está acá nada más
            # para detectar el cierre de la conexión; ping/pong ya lo
            # maneja uvicorn/websockets por su cuenta.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await gestor.desconectar(claims.organization_id, websocket)


@app.post("/internal/eventos/", dependencies=[Depends(requerir_servicio_interno)], response_model=EventoRecibidoResponse)
async def recibir_evento(evento: EventoConversacion) -> EventoRecibidoResponse:
    entregados = await gestor.transmitir(evento.organization_id, evento.model_dump())
    return EventoRecibidoResponse(entregados=entregados)


@app.get("/organizations/{organization_id}/conexiones-activas", response_model=ConexionesActivasResponse)
async def conexiones_activas(organization_id: int, claims=Depends(operador_autenticado)) -> ConexionesActivasResponse:
    if claims.organization_id != organization_id:
        raise HTTPException(status_code=403, detail="No podés ver las conexiones de otra organización.")
    return ConexionesActivasResponse(conectados=gestor.conectados(organization_id))
