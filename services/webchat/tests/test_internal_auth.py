import pytest
from fastapi import HTTPException

from app.config import settings
from app.internal_auth import verify_service_token


@pytest.fixture
def token_configurado(monkeypatch):
    monkeypatch.setattr(settings, "CORE_SERVICE_TOKEN", "el-token-correcto")
    return settings.CORE_SERVICE_TOKEN


def test_token_correcto_pasa(token_configurado):
    assert verify_service_token(authorization="Service-Token el-token-correcto") is True


def test_token_incorrecto_da_403(token_configurado):
    with pytest.raises(HTTPException) as exc_info:
        verify_service_token(authorization="Service-Token token-equivocado")
    assert exc_info.value.status_code == 403


def test_formato_invalido_da_401(token_configurado):
    with pytest.raises(HTTPException) as exc_info:
        verify_service_token(authorization="Bearer el-token-correcto")
    assert exc_info.value.status_code == 401


def test_sin_espacio_en_el_header_da_401(token_configurado):
    with pytest.raises(HTTPException) as exc_info:
        verify_service_token(authorization="Service-Tokenel-token-correcto")
    assert exc_info.value.status_code == 401


def test_header_vacio_da_401(token_configurado):
    with pytest.raises(HTTPException) as exc_info:
        verify_service_token(authorization="")
    assert exc_info.value.status_code == 401


def test_sin_token_configurado_en_el_servicio_da_500(monkeypatch):
    monkeypatch.setattr(settings, "CORE_SERVICE_TOKEN", "")
    with pytest.raises(HTTPException) as exc_info:
        verify_service_token(authorization="Service-Token lo-que-sea")
    assert exc_info.value.status_code == 500
