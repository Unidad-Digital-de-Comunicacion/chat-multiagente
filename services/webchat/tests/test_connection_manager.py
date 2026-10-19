import asyncio

import pytest

from app.connection_manager import ConnectionManager


class FakeWebSocket:
    """Doble liviano de `fastapi.WebSocket` — sólo lo que usa
    `ConnectionManager` (accept/close/send_text), sin un scope ASGI real."""

    def __init__(self, fallar_al_enviar=False):
        self.accepted = False
        self.closed = False
        self.close_code = None
        self.sent = []
        self._fallar_al_enviar = fallar_al_enviar

    async def accept(self):
        self.accepted = True

    async def close(self, code=1000, reason=None):
        self.closed = True
        self.close_code = code

    async def send_text(self, data):
        if self._fallar_al_enviar:
            raise RuntimeError("socket cerrado del otro lado")
        self.sent.append(data)


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def manager():
    return ConnectionManager()


def test_connect_acepta_y_registra_el_websocket(manager):
    ws = FakeWebSocket()

    _run(manager.connect("v-1", ws))

    assert ws.accepted is True
    assert manager.is_connected("v-1") is True


def test_connect_repetido_cierra_la_conexion_anterior(manager):
    ws_vieja = FakeWebSocket()
    ws_nueva = FakeWebSocket()

    _run(manager.connect("v-1", ws_vieja))
    _run(manager.connect("v-1", ws_nueva))

    assert ws_vieja.closed is True
    assert manager.active_connections["v-1"] is ws_nueva


def test_disconnect_solo_borra_si_es_el_mismo_websocket(manager):
    ws_vieja = FakeWebSocket()
    ws_nueva = FakeWebSocket()
    _run(manager.connect("v-1", ws_vieja))
    manager.active_connections["v-1"] = ws_nueva

    manager.disconnect("v-1", ws_vieja)

    # ws_vieja ya no es la conexión activa — no debe borrar la nueva
    assert manager.is_connected("v-1") is True
    assert manager.active_connections["v-1"] is ws_nueva


def test_disconnect_borra_la_conexion_activa(manager):
    ws = FakeWebSocket()
    _run(manager.connect("v-1", ws))

    manager.disconnect("v-1", ws)

    assert manager.is_connected("v-1") is False


def test_send_to_visitor_entrega_el_payload_si_esta_conectado(manager):
    ws = FakeWebSocket()
    _run(manager.connect("v-1", ws))

    entregado = _run(manager.send_to_visitor("v-1", {"tipo": "mensaje_bot", "texto": "hola"}))

    assert entregado is True
    assert ws.sent == ['{"tipo": "mensaje_bot", "texto": "hola"}']


def test_send_to_visitor_devuelve_false_si_no_esta_conectado(manager):
    entregado = _run(manager.send_to_visitor("v-ausente", {"tipo": "mensaje_bot", "texto": "hola"}))

    assert entregado is False


def test_send_to_visitor_desconecta_si_falla_el_envio(manager):
    ws = FakeWebSocket(fallar_al_enviar=True)
    _run(manager.connect("v-1", ws))

    entregado = _run(manager.send_to_visitor("v-1", {"tipo": "mensaje_bot", "texto": "hola"}))

    assert entregado is False
    assert manager.is_connected("v-1") is False


def test_is_connected_refleja_el_estado_actual(manager):
    assert manager.is_connected("v-1") is False
    ws = FakeWebSocket()
    _run(manager.connect("v-1", ws))
    assert manager.is_connected("v-1") is True
