import time

import httpx
import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jwt.algorithms import RSAAlgorithm

from app import auth as auth_module
from app.config import get_settings
from app.http_client import get_http_client
from app.main import app


class FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)


class FakeAsyncClient:
    """Sólo necesita `get` — este servicio no manda ningún POST saliente,
    únicamente pide el JWKS de Core (`app.auth`). Mismo patrón de
    inyección vía `app.dependency_overrides[get_http_client]` que
    `channel-gateway/tests/conftest.py`, en vez de parchear un import."""

    def __init__(self, jwks_response):
        self.calls = []
        self.jwks_response = jwks_response

    async def get(self, url, **kwargs):
        self.calls.append(url)
        return self.jwks_response


@pytest.fixture(autouse=True)
def _resetear_cache_jwks():
    """La clave pública se cachea a nivel de módulo en `app.auth` (dura
    todo el proceso, no por request) — sin este reset, el primer test que
    la llena dejaría a los siguientes sin pasar de nuevo por
    `FakeAsyncClient`, y un test que espera un JWKS vacío/roto heredaría
    la clave válida de uno anterior."""
    auth_module._cache["clave"] = None
    auth_module._cache["obtenida_at"] = 0.0
    yield


@pytest.fixture
def clave_rsa():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def jwks_response(clave_rsa):
    jwk = RSAAlgorithm.to_jwk(clave_rsa.public_key(), as_dict=True)
    return FakeResponse(200, {"keys": [jwk]})


@pytest.fixture
def fake_http_client(jwks_response):
    fake = FakeAsyncClient(jwks_response)
    app.dependency_overrides[get_http_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_http_client, None)


@pytest.fixture
def client(fake_http_client):
    # `with` (no un `TestClient(app)` suelto) para que el `lifespan` corra
    # Y todas las llamadas —HTTP y WebSocket— de este cliente compartan un
    # solo event loop: `connections.GestorConexiones` usa un `asyncio.Lock`
    # que si no podría terminar atado a un loop distinto entre una llamada
    # y otra.
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def hacer_token(clave_rsa):
    def _hacer(*, user_id=42, org_id=7, grupos=None, email="operador@test.com", exp_en_segundos=1800):
        payload = {
            "user_id": user_id, "org_id": org_id, "grupos": grupos or ["operadores"], "email": email,
            "exp": int(time.time()) + exp_en_segundos,
        }
        return pyjwt.encode(payload, clave_rsa, algorithm="RS256")

    return _hacer


@pytest.fixture
def core_service_token():
    settings = get_settings()
    anterior = settings.core_service_token
    settings.core_service_token = "el-token-interno-de-prueba"
    yield settings.core_service_token
    settings.core_service_token = anterior
