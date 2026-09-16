"""Contrato del único evento que este servicio sabe recibir de Core
(`POST /internal/eventos/`, ver `internal_auth.py`) y reenviar por
WebSocket — deliberadamente mínimo: nunca el contenido real de un mensaje
u observación, sólo "algo cambió en esta conversación, andá a buscarlo por
REST a Core" (mismo criterio que la sección "Notificaciones push" de
docs/operators-desk-api-contract.md). `team_id`/`operador_id` son
opcionales y sólo informativos — hoy el reenvío es por organización
completa (ver `connections.py`), el cliente decide con esto si le importa
o no refrescar lo que tiene en pantalla."""
from typing import Literal

from pydantic import BaseModel

TipoEvento = Literal["mensaje_nuevo", "conversacion_actualizada", "nota_interna_nueva"]


class EventoConversacion(BaseModel):
    tipo: TipoEvento
    organization_id: int
    conversacion_id: int
    team_id: int | None = None
    operador_id: int | None = None
