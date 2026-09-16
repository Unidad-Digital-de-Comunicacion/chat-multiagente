from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from .config import get_settings
from .messages import router as messages_router
from .webhooks import router as webhooks_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    async with httpx.AsyncClient(timeout=settings.http_timeout_segundos) as client:
        app.state.http_client = client
        yield


app = FastAPI(title="Channel Gateway Service", lifespan=lifespan)
app.include_router(webhooks_router)
app.include_router(messages_router)


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")
