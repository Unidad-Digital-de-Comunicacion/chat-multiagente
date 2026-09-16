"""Valida el JWT (RS256) que manda un operador al conectarse — mismo JWKS
público que ya expone Core para el resto de los servicios FastAPI
(`JWT_PUBLIC_KEY_URL`, ver `config.py` y el ancla `fastapi-common` de
docker-compose.yml). Hoy hay una sola clave activa en todo el sistema
(`authentication.keys.KID`, Core no soporta rotación todavía) — por eso
alcanza con cachear esa única clave en memoria de proceso y sólo
refrescarla si una verificación falla (por si el volumen `jwt_keys` se
regeneró, ej. tras borrar el volumen en dev)."""
import time
from dataclasses import dataclass

import httpx
import jwt
from fastapi import Depends, Header, HTTPException
from jwt.algorithms import RSAAlgorithm

from .config import get_settings
from .http_client import get_http_client

_TTL_SEGUNDOS = 300

# Cache a nivel de módulo (no una instancia por request) a propósito: la
# clave pública de Core es la misma para todo el proceso, no por
# conexión — un dict simple alcanza, no hace falta una clase para esto.
_cache: dict = {"clave": None, "obtenida_at": 0.0}


@dataclass(frozen=True)
class OperadorClaims:
    user_id: int
    organization_id: int
    grupos: list[str]
    email: str


async def _obtener_clave_publica(client: httpx.AsyncClient, *, forzar_refresh: bool = False):
    ahora = time.monotonic()
    vencida = (ahora - _cache["obtenida_at"]) > _TTL_SEGUNDOS
    if forzar_refresh or _cache["clave"] is None or vencida:
        settings = get_settings()
        respuesta = await client.get(settings.jwt_public_key_url)
        respuesta.raise_for_status()
        claves = respuesta.json().get("keys") or []
        if not claves:
            raise RuntimeError("Core todavía no publicó ninguna clave en su JWKS.")
        _cache["clave"] = RSAAlgorithm.from_jwk(claves[0])
        _cache["obtenida_at"] = ahora
    return _cache["clave"]


def _claims_desde_payload(payload: dict) -> OperadorClaims:
    return OperadorClaims(
        user_id=int(payload["user_id"]), organization_id=int(payload["org_id"]),
        grupos=payload.get("grupos", []), email=payload.get("email", ""),
    )


async def verificar_token(token: str, client: httpx.AsyncClient) -> OperadorClaims:
    """Levanta `jwt.InvalidTokenError` (o una subclase, ej. `ExpiredSignatureError`)
    si el token no es válido — quien llama decide qué código HTTP/WS
    devolver. Reintenta una vez refrescando la clave por si Core la rotó."""
    for intento in range(2):
        try:
            clave = await _obtener_clave_publica(client, forzar_refresh=intento == 1)
            payload = jwt.decode(token, clave, algorithms=["RS256"])
            return _claims_desde_payload(payload)
        except jwt.InvalidTokenError:
            if intento == 1:
                raise
    raise jwt.InvalidTokenError("No se pudo verificar el token.")


async def operador_autenticado(
    authorization: str | None = Header(default=None), client: httpx.AsyncClient = Depends(get_http_client),
) -> OperadorClaims:
    """Dependencia HTTP (no WebSocket) para `GET /organizations/{id}/
    conexiones-activas` — la ruta WS usa `verificar_token` directo porque
    el token le llega por la URL, no por header (ver `main.py`)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Falta el header Authorization: Bearer <token>.")
    token = authorization[len("Bearer "):].strip()
    try:
        return await verificar_token(token, client)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido o vencido.")
