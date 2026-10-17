from fastapi import APIRouter
from app.schemas import SessionInitRequest, SessionInitResponse
from app.core_client import core_client

router = APIRouter(prefix="/sessions", tags=["Sesiones"])

@router.post("/", response_model=SessionInitResponse)
async def inicializar_sesion(payload: SessionInitRequest):
    """
    Inicializa o recupera una sesión para un visitor_id y organization_id.
    Si Core tiene historial previo para este contacto externo, lo recupera para
    repoblar el widget al recargar la página.
    """
    historial = await core_client.obtener_historial_sesion(
        organization_id=payload.organization_id,
        visitor_id=payload.visitor_id
    )

    return SessionInitResponse(
        status="active",
        organization_id=payload.organization_id,
        visitor_id=payload.visitor_id,
        historial=historial
    )
