from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class MenuOption(BaseModel):
    id: str
    titulo: str

class BotAction(BaseModel):
    tipo: str
    texto: Optional[str] = None
    encabezado: Optional[str] = None
    opciones: Optional[List[MenuOption]] = None

# Handshake / Sesión
class SessionInitRequest(BaseModel):
    organization_id: int
    visitor_id: str
    nombre: Optional[str] = None
    telefono: Optional[str] = None

class SessionInitResponse(BaseModel):
    status: str = "active"
    organization_id: int
    visitor_id: str
    historial: List[Dict[str, Any]] = Field(default_factory=list)

# Mensaje enviado por el visitante desde el widget
class MensajeVisitanteRequest(BaseModel):
    organization_id: int
    visitor_id: str
    texto: str = Field(..., min_length=1, max_length=2000)

class MensajeVisitanteResponse(BaseModel):
    status: str = "ok"
    acciones: List[Dict[str, Any]] = Field(default_factory=list)

# Mensaje enviado por Core (operador humano en Operators Desk) hacia Webchat
class MensajeOperadorRequest(BaseModel):
    visitor_id: str
    texto: str

class MensajeOperadorResponse(BaseModel):
    status: str
    delivered: bool
