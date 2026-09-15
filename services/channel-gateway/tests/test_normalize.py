from app.normalize import normalizar_mensajes


def test_normaliza_un_mensaje_de_texto():
    payload = {
        "object": "page",
        "entry": [{
            "id": "PAGE_ID",
            "time": 1520383988285,
            "messaging": [{
                "sender": {"id": "PSID123"},
                "recipient": {"id": "PAGE_ID"},
                "timestamp": 1520383988285,
                "message": {"mid": "mid.123", "text": "Hola, quiero hacer una consulta"},
            }],
        }],
    }
    mensajes = normalizar_mensajes("messenger", payload)
    assert len(mensajes) == 1
    assert mensajes[0].remitente_id == "PSID123"
    assert mensajes[0].texto == "Hola, quiero hacer una consulta"
    assert mensajes[0].canal_tipo == "messenger"
    assert mensajes[0].timestamp_ms == 1520383988285


def test_ignora_eco_de_mensajes_propios():
    payload = {"entry": [{"messaging": [{
        "sender": {"id": "PAGE_ID"},
        "message": {"mid": "mid.1", "text": "Gracias por escribirnos", "is_echo": True},
    }]}]}
    assert normalizar_mensajes("messenger", payload) == []


def test_ignora_eventos_sin_texto_delivery_receipts():
    payload = {"entry": [{"messaging": [{
        "sender": {"id": "PSID123"},
        "delivery": {"mids": ["mid.1"], "watermark": 1520383988285},
    }]}]}
    assert normalizar_mensajes("messenger", payload) == []


def test_varios_mensajes_en_el_mismo_payload():
    payload = {"entry": [
        {"messaging": [{"sender": {"id": "A"}, "message": {"text": "uno"}}]},
        {"messaging": [{"sender": {"id": "B"}, "message": {"text": "dos"}}]},
    ]}
    mensajes = normalizar_mensajes("instagram", payload)
    assert [m.remitente_id for m in mensajes] == ["A", "B"]
    assert all(m.canal_tipo == "instagram" for m in mensajes)


def test_payload_vacio_no_rompe():
    assert normalizar_mensajes("messenger", {}) == []


def test_normaliza_un_mensaje_de_whatsapp():
    payload = {
        "entry": [{"id": "WABA_ID", "changes": [{"field": "messages", "value": {
            "messaging_product": "whatsapp",
            "metadata": {"display_phone_number": "5493511234567", "phone_number_id": "111"},
            "contacts": [{"profile": {"name": "Juan"}, "wa_id": "5493511234567"}],
            "messages": [{
                "from": "5493511234567", "id": "wamid.1", "timestamp": "1700000000",
                "text": {"body": "Hola, quiero hacer una consulta"}, "type": "text",
            }],
        }}]}],
    }
    mensajes = normalizar_mensajes("whatsapp", payload)
    assert len(mensajes) == 1
    assert mensajes[0].remitente_id == "5493511234567"
    assert mensajes[0].texto == "Hola, quiero hacer una consulta"
    assert mensajes[0].canal_tipo == "whatsapp"
    assert mensajes[0].timestamp_ms == 1700000000000


def test_whatsapp_ignora_eventos_de_status_delivery_read():
    payload = {
        "entry": [{"changes": [{"field": "messages", "value": {
            "statuses": [{"id": "wamid.1", "status": "delivered", "timestamp": "1700000000"}],
        }}]}],
    }
    assert normalizar_mensajes("whatsapp", payload) == []


def test_whatsapp_ignora_mensajes_que_no_son_de_texto():
    payload = {
        "entry": [{"changes": [{"field": "messages", "value": {
            "messages": [{"from": "5493511234567", "type": "image", "image": {"id": "abc"}}],
        }}]}],
    }
    assert normalizar_mensajes("whatsapp", payload) == []


def test_whatsapp_ignora_changes_que_no_son_de_mensajes():
    payload = {"entry": [{"changes": [{"field": "message_template_status_update", "value": {}}]}]}
    assert normalizar_mensajes("whatsapp", payload) == []
