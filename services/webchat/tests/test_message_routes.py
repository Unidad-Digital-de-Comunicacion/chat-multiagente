import pytest

from app.connection_manager import manager
from app.core_client import core_client


@pytest.fixture
def fake_send_to_visitor(monkeypatch):
    """Reemplaza `manager.send_to_visitor` por una versión que sólo graba
    las llamadas — evita depender de un WebSocket real conectado y permite
    verificar exactamente qué payload armaron las rutas."""
    calls = []

    async def _fake(visitor_id, payload):
        calls.append((visitor_id, payload))
        return True

    monkeypatch.setattr(manager, "send_to_visitor", _fake)
    return calls


def test_mensaje_visitante_reenvia_texto_por_websocket(client, monkeypatch, fake_send_to_visitor):
    async def _fake_enviar(organization_id, visitor_id, texto):
        return [{"tipo": "enviar_texto", "texto": "Hola, en que te ayudamos?"}]

    monkeypatch.setattr(core_client, "enviar_mensaje_entrante", _fake_enviar)

    response = client.post("/mensajes/", json={"organization_id": 1, "visitor_id": "v-1", "texto": "hola"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["acciones"] == [{"tipo": "enviar_texto", "texto": "Hola, en que te ayudamos?"}]
    assert fake_send_to_visitor == [
        ("v-1", {"tipo": "mensaje_bot", "texto": "Hola, en que te ayudamos?"}),
    ]


def test_mensaje_visitante_reenvia_menu_por_websocket(client, monkeypatch, fake_send_to_visitor):
    async def _fake_enviar(organization_id, visitor_id, texto):
        return [{
            "tipo": "mostrar_menu",
            "texto": "Elegi una opcion",
            "encabezado": "Menu principal",
            "opciones": [{"id": "1", "titulo": "Ventas"}],
        }]

    monkeypatch.setattr(core_client, "enviar_mensaje_entrante", _fake_enviar)

    response = client.post("/mensajes/", json={"organization_id": 1, "visitor_id": "v-2", "texto": "hola"})

    assert response.status_code == 200
    visitor_id, payload = fake_send_to_visitor[0]
    assert visitor_id == "v-2"
    assert payload["tipo"] == "menu"
    assert payload["encabezado"] == "Menu principal"
    assert payload["opciones"] == [{"id": "1", "titulo": "Ventas"}]


def test_mensaje_visitante_reenvia_acciones_desconocidas_tal_cual(client, monkeypatch, fake_send_to_visitor):
    async def _fake_enviar(organization_id, visitor_id, texto):
        return [{"tipo": "derivar_equipo", "equipo": "Ventas"}]

    monkeypatch.setattr(core_client, "enviar_mensaje_entrante", _fake_enviar)

    response = client.post("/mensajes/", json={"organization_id": 1, "visitor_id": "v-3", "texto": "hola"})

    assert response.status_code == 200
    assert fake_send_to_visitor == [("v-3", {"tipo": "derivar_equipo", "equipo": "Ventas"})]


def test_mensaje_visitante_sin_acciones_no_envia_nada_por_websocket(client, monkeypatch, fake_send_to_visitor):
    async def _sin_acciones(organization_id, visitor_id, texto):
        return []

    monkeypatch.setattr(core_client, "enviar_mensaje_entrante", _sin_acciones)

    response = client.post("/mensajes/", json={"organization_id": 1, "visitor_id": "v-4", "texto": "hola"})

    assert response.status_code == 200
    assert response.json()["acciones"] == []
    assert fake_send_to_visitor == []


def test_mensaje_visitante_requiere_texto_no_vacio(client):
    response = client.post("/mensajes/", json={"organization_id": 1, "visitor_id": "v-5", "texto": ""})

    assert response.status_code == 422


def test_mensaje_operador_requiere_header_de_autorizacion(client):
    # El header es obligatorio en la firma del endpoint (`Header(...)`) —
    # FastAPI corta con 422 antes de que `verify_service_token` corra.
    response = client.post("/messages/send", json={"visitor_id": "v-1", "texto": "hola"})

    assert response.status_code == 422


def test_mensaje_operador_con_token_invalido_da_403(client, core_service_token):
    response = client.post(
        "/messages/send",
        json={"visitor_id": "v-1", "texto": "hola"},
        headers={"Authorization": "Service-Token token-incorrecto"},
    )

    assert response.status_code == 403


def test_mensaje_operador_entregado_si_el_visitante_esta_conectado(client, core_service_token, fake_send_to_visitor):
    response = client.post(
        "/messages/send",
        json={"visitor_id": "v-1", "texto": "Hola, soy un operador"},
        headers={"Authorization": f"Service-Token {core_service_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "delivered"
    assert data["delivered"] is True
    assert fake_send_to_visitor == [
        ("v-1", {"tipo": "mensaje_operador", "texto": "Hola, soy un operador"}),
    ]


def test_mensaje_operador_queda_queued_si_el_visitante_no_esta_conectado(client, core_service_token, monkeypatch):
    async def _no_conectado(visitor_id, payload):
        return False

    monkeypatch.setattr(manager, "send_to_visitor", _no_conectado)

    response = client.post(
        "/messages/send",
        json={"visitor_id": "v-ausente", "texto": "hola"},
        headers={"Authorization": f"Service-Token {core_service_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"
    assert data["delivered"] is False
