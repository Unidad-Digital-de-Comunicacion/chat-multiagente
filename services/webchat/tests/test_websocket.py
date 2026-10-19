import pytest
from fastapi import WebSocketDisconnect

from app.connection_manager import manager


def test_conectar_recibe_confirmacion(client):
    with client.websocket_connect("/ws/visitante/v-1") as websocket:
        mensaje = websocket.receive_json()
        assert mensaje == {"tipo": "conexion_establecida", "visitor_id": "v-1"}


def test_ping_responde_pong(client):
    with client.websocket_connect("/ws/visitante/v-1") as websocket:
        websocket.receive_json()  # conexion_establecida
        websocket.send_text("ping")
        assert websocket.receive_text() == "pong"


def test_desconectar_borra_la_conexion_del_manager(client):
    with client.websocket_connect("/ws/visitante/v-2") as websocket:
        websocket.receive_json()  # conexion_establecida
        assert manager.is_connected("v-2") is True

    assert manager.is_connected("v-2") is False


def test_segunda_conexion_del_mismo_visitante_cierra_la_anterior(client):
    with client.websocket_connect("/ws/visitante/v-3") as ws_vieja:
        ws_vieja.receive_json()  # conexion_establecida

        with client.websocket_connect("/ws/visitante/v-3") as ws_nueva:
            ws_nueva.receive_json()  # conexion_establecida

            with pytest.raises(WebSocketDisconnect):
                ws_vieja.receive_text()
