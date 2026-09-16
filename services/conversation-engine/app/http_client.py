"""Mismo patrón de inyección de dependencias que `channel-gateway/app/
http_client.py`: un único `httpx.AsyncClient` compartido, creado una vez
en el `lifespan` de `main.py` (`app.state.http_client`) e inyectado acá
— permite testear `auth.verificar_token` (que lo usa para pedir el JWKS
de Core) con `app.dependency_overrides` en vez de mockear `httpx.
AsyncClient` por import path."""
import httpx
from fastapi import Request


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client
