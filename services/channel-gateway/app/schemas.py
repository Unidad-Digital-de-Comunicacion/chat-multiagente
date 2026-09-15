"""Modelos de datos internos — no hace falta pydantic acá (no son bodies de
request/response de FastAPI, sólo estructuras que se pasan entre módulos
propios), un dataclass simple alcanza."""
from dataclasses import dataclass


@dataclass(frozen=True)
class CanalConfig:
    """Lo que devuelve `GET /api/core/internal/canales/<uuid>/` en Core —
    ver `channels.views.InternalCanalConfigView`. `telefono_id` sólo se usa
    (y sólo viene con valor) para WhatsApp — ver `meta_client.
    enviar_texto_whatsapp`."""

    organization_id: int
    tipo: str
    api_key: str
    webhook_secret: str
    activo: bool
    telefono_id: str = ""


@dataclass(frozen=True)
class MensajeEntrante:
    """Un mensaje normalizado, ya independiente del formato particular de
    cada canal — lo que se manda a `POST /api/core/bot/mensaje-entrante/`
    (sección 4.1 de docs/CONTEXTO_PROYECTO.md, `conversations.views.
    MensajeEntranteView` del lado de Core)."""

    canal_tipo: str
    remitente_id: str
    texto: str
    timestamp_ms: int
