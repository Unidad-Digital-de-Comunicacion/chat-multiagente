import pytest
from fastapi import WebSocketDisconnect

from app.http_client import get_http_client
from app.main import app
from tests.conftest import FakeAsyncClient, FakeResponse


class TestJWKSVacio:
    """Core sin ninguna clave publicada todavía (JWKS `{"keys": []}`) — no
    debería poder pasar nunca en un ambiente andando, pero el fallo tiene
    que ser explícito, no una excepción rara sin explicar en el medio."""

    def test_ws_lo_rechaza_igual_que_un_token_invalido(self, client, hacer_token):
        import app.auth as auth_module

        # Reemplaza el `FakeAsyncClient` de la fixture `fake_http_client`
        # por uno que devuelve un JWKS vacío — la fixture igual saca el
        # override al terminar el test (`pop`), no hace falta restaurarlo acá.
        app.dependency_overrides[get_http_client] = lambda: FakeAsyncClient(FakeResponse(200, {"keys": []}))

        token = hacer_token(org_id=7)
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f"/ws/operador/{token}"):
                pass

        # No debería haber quedado nada cacheado de un intento fallido.
        assert auth_module._cache["clave"] is None
