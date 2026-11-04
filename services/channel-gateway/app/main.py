import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from .config import get_settings
from .messages import router as messages_router
from .observabilidad import MiddlewareRequestId, configurar_logging, propagar_request_id
from .webhooks import router as webhooks_router

# (Reemplazado por `observabilidad.configurar_logging`, JSON a stdout + archivo
# rotativo en LOG_DIR; el motivo original sigue valiendo:)
# Sin esto, todo `logger.info(...)` de `channel_gateway.*` (webhooks.py,
# normalize.py) queda descartado en silencio — el root logger de Python no
# tiene ningún handler configurado acá (uvicorn sólo configura SUS propios
# loggers, `uvicorn.access`/`uvicorn.error`, no el resto), y sin handler el
# nivel efectivo por default es WARNING. Confirmado en vivo en producción
# (2026-09-20): "mensaje entrante"/"se ignora" nunca se vieron en
# `docker compose logs`, sólo los `.warning()` (por el `lastResort` handler
# automático de Python, que sólo cubre WARNING para arriba).
configurar_logging("channel-gateway")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    async with httpx.AsyncClient(
        timeout=settings.http_timeout_segundos, event_hooks={"request": [propagar_request_id]},
    ) as client:
        app.state.http_client = client
        yield


app = FastAPI(title="Channel Gateway Service", lifespan=lifespan)
app.add_middleware(MiddlewareRequestId)
app.include_router(webhooks_router)
app.include_router(messages_router)


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
