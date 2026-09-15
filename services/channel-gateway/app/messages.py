"""Envío de mensajes salientes. Hoy lo llama `conversations.channel_gateway_
client.enviar_mensaje_saliente` de Core cuando un operador responde o cierra
una conversación (`ConversacionViewSet.responder`/`cerrar`) — Conversation
Engine (Fase 4, la versión "real" con WebSocket/asignación round-robin)
sigue sin existir, ver docs/CONTEXTO_PROYECTO.md. Protegido con `internal_
auth.requerir_servicio_interno` — a diferencia de `/webhooks/*` (a
propósito público, lo llama Meta), esto sólo debería poder llamarlo OTRO
servicio interno del proyecto."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .core_client import CanalNoEncontrado, CoreNoDisponible, obtener_canal
from .internal_auth import requerir_servicio_interno
from .meta_client import EnvioFallido, enviar_texto_por_canal

router = APIRouter()

_TIPOS_CON_ENVIO = {"MESSENGER", "INSTAGRAM", "WHATSAPP"}


class EnviarMensajeRequest(BaseModel):
    canal_uuid: str
    destinatario_id: str
    texto: str


@router.post("/messages/send", dependencies=[Depends(requerir_servicio_interno)])
async def enviar_mensaje(body: EnviarMensajeRequest):
    try:
        canal = await obtener_canal(body.canal_uuid)
    except CanalNoEncontrado:
        raise HTTPException(status_code=404, detail="No existe ese canal.")
    except CoreNoDisponible as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if canal.tipo not in _TIPOS_CON_ENVIO:
        raise HTTPException(status_code=400, detail=f"{canal.tipo} todavía no soporta envío desde acá.")
    if not canal.activo:
        raise HTTPException(status_code=400, detail="El canal está desactivado.")

    try:
        resultado = await enviar_texto_por_canal(canal, body.destinatario_id, body.texto)
    except EnvioFallido as exc:
        raise HTTPException(status_code=502, detail=exc.detalle)
    return {"status": "ok", "graph_api_response": resultado}
