from app.core_client import core_client


def test_inicializar_sesion_devuelve_historial_de_core(client, monkeypatch):
    async def _fake_historial(organization_id, visitor_id):
        assert organization_id == 1
        assert visitor_id == "v-1"
        return [{"texto": "hola", "autor": "bot"}]

    monkeypatch.setattr(core_client, "obtener_historial_sesion", _fake_historial)

    response = client.post("/sessions/", json={"organization_id": 1, "visitor_id": "v-1"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "active"
    assert data["organization_id"] == 1
    assert data["visitor_id"] == "v-1"
    assert data["historial"] == [{"texto": "hola", "autor": "bot"}]


def test_inicializar_sesion_sin_historial_previo(client, monkeypatch):
    async def _sin_historial(organization_id, visitor_id):
        return []

    monkeypatch.setattr(core_client, "obtener_historial_sesion", _sin_historial)

    response = client.post(
        "/sessions/",
        json={"organization_id": 1, "visitor_id": "v-2", "nombre": "Ana"},
    )

    assert response.status_code == 200
    assert response.json()["historial"] == []


def test_inicializar_sesion_requiere_organization_id_y_visitor_id(client):
    response = client.post("/sessions/", json={"visitor_id": "v-3"})

    assert response.status_code == 422
