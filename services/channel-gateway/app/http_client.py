"""Cliente `httpx.AsyncClient` compartido por toda la app — se crea una
sola vez en el `lifespan` de `main.py` (pooling de conexiones real, en vez
de una por request) y vive en `app.state.http_client`. `get_http_client` es
la dependencia de FastAPI que lo inyecta en cada endpoint; de ahí baja como
parámetro explícito a `core_client`/`meta_client`. Este es el seam real
para los tests: pasan un cliente falso directamente, no parchean el import
global `httpx.AsyncClient`."""
import httpx
from fastapi import Request


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client
