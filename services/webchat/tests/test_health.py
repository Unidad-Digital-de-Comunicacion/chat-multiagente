def test_health_devuelve_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "webchat"
    assert "core_url" in data
