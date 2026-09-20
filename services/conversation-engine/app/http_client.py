"""Mismo patrón de inyección de dependencias que `channel-gateway/app/
http_client.py`: un único `httpx.AsyncClient` compartido, creado una vez
en el `lifespan` de `main.py` (`app.state.http_client`) e inyectado acá
— permite testear `auth.verificar_token` (que lo usa para pedir el JWKS
de Core) con `app.dependency_overrides` en vez de mockear `httpx.
AsyncClient` por import path.

A diferencia de channel-gateway, esta dependencia se usa también desde
`main.ws_operador` — una ruta WebSocket, que no tiene un `Request` real
(no hay handshake HTTP de verdad en el scope de FastAPI). Tipar el
parámetro como `HTTPConnection` (la clase base común de `Request` y
`WebSocket`, ambas con `.app`/`.state`) es lo que permite que FastAPI
inyecte esto en los dos tipos de ruta — con `Request` acá, cualquier
llamada desde la ruta WS reventaba con
`TypeError: get_http_client() missing 1 required positional argument`
ANTES de llegar a validar el token (bug real, encontrado 2026-09-20 vía
`Error_Sockets_UDC_Chat.ipynb`: la ruta WS devolvía 500 tanto con token
válido como inválido)."""
import httpx
from starlette.requests import HTTPConnection


def get_http_client(conn: HTTPConnection) -> httpx.AsyncClient:
    return conn.app.state.http_client
