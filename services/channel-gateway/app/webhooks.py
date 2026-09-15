"""Recepción de webhooks de Meta para Messenger, Instagram y WhatsApp. Cada
canal tiene su propia URL (`/webhooks/<tipo>/<canal_uuid>/`, con el mismo
`uuid` que expone `channels.CanalSerializer.webhook_url` en Core) y su
propio `webhook_secret` — ver `app/security.py` para por qué eso es un
secreto aparte de `META_APP_SECRET`.

Cada mensaje normalizado se manda a Core (`core_client.
enviar_mensaje_entrante`, sección 4.1 de docs/CONTEXTO_PROYECTO.md) — Core
decide qué hacer (hoy: crear/continuar la `Conversacion` y devolver el
mensaje de bienvenida en el primer contacto) y este servicio sólo ejecuta
las `acciones` que devuelve, mandándolas por el canal correspondiente. El
árbol de menú (`MenuOpcion`) todavía no se recorre del lado de Core — ver
el docstring de `conversations.models` para el detalle de qué falta."""
import logging

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse

from .config import get_settings
from .core_client import CanalNoEncontrado, CoreNoDisponible, enviar_mensaje_entrante, obtener_canal
from .meta_client import EnvioFallido, enviar_texto_por_canal
from .normalize import normalizar_mensajes
from .security import verificar_firma, verificar_verify_token

logger = logging.getLogger("channel_gateway.webhooks")

router = APIRouter()

_TIPOS_SOPORTADOS = {"messenger": "MESSENGER", "instagram": "INSTAGRAM", "whatsapp": "WHATSAPP"}


def _tipo_o_404(canal_tipo_url: str) -> str:
    tipo = _TIPOS_SOPORTADOS.get(canal_tipo_url)
    if tipo is None:
        raise HTTPException(status_code=404, detail="Canal no soportado (todavía) o inexistente.")
    return tipo


async def _canal_o_404(canal_uuid: str, tipo_esperado: str):
    try:
        canal = await obtener_canal(canal_uuid)
    except CanalNoEncontrado:
        raise HTTPException(status_code=404, detail="No existe ese canal.")
    except CoreNoDisponible as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if canal.tipo != tipo_esperado:
        raise HTTPException(status_code=404, detail="No existe ese canal.")
    return canal


@router.get("/webhooks/{canal_tipo_url}/{canal_uuid}")
async def verificar_suscripcion(canal_tipo_url: str, canal_uuid: str, request: Request):
    """El handshake que Meta hace UNA vez al configurar el webhook: si
    `hub.verify_token` coincide con el `webhook_secret` de este canal,
    contesta con `hub.challenge` tal cual (texto plano, no JSON — así lo
    exige Meta)."""
    tipo = _tipo_o_404(canal_tipo_url)
    canal = await _canal_o_404(canal_uuid, tipo)
    params = request.query_params
    if params.get("hub.mode") != "subscribe":
        raise HTTPException(status_code=403, detail="hub.mode inválido.")
    if not verificar_verify_token(params.get("hub.verify_token", ""), canal.webhook_secret):
        raise HTTPException(status_code=403, detail="hub.verify_token inválido.")
    return PlainTextResponse(params.get("hub.challenge", ""))


@router.post("/webhooks/{canal_tipo_url}/{canal_uuid}")
async def recibir_evento(
    canal_tipo_url: str, canal_uuid: str, request: Request,
    x_hub_signature_256: str | None = Header(default=None),
):
    """Cada mensaje/evento real. Firmado por Meta con `X-Hub-Signature-256`
    sobre el body crudo — se verifica ANTES de tocar el JSON, para no
    procesar nada que no venga realmente de Meta."""
    tipo = _tipo_o_404(canal_tipo_url)
    raw_body = await request.body()
    settings = get_settings()
    if not verificar_firma(raw_body, x_hub_signature_256, settings.meta_app_secret):
        raise HTTPException(status_code=403, detail="Firma inválida.")

    canal = await _canal_o_404(canal_uuid, tipo)
    payload = await request.json()
    mensajes = normalizar_mensajes(canal_tipo_url, payload)
    for mensaje in mensajes:
        logger.info(
            "mensaje entrante organization_id=%s canal=%s remitente=%s",
            canal.organization_id, mensaje.canal_tipo, mensaje.remitente_id,
        )
        acciones = await enviar_mensaje_entrante(
            organization_id=canal.organization_id, channel=canal.tipo,
            contact_externo_id=mensaje.remitente_id, texto=mensaje.texto,
        )
        for accion in acciones:
            if accion.get("tipo") != "enviar_texto":
                continue
            try:
                await enviar_texto_por_canal(canal, mensaje.remitente_id, accion["texto"])
            except EnvioFallido as exc:
                # No hay nada mejor que hacer del lado de Meta si esto falla
                # (ej. api_key vencida) — Meta ya recibió su 200 más abajo
                # pase lo que pase acá, así que sólo queda loguearlo.
                logger.warning(
                    "no se pudo ejecutar la acción enviar_texto organization_id=%s canal=%s: %s",
                    canal.organization_id, mensaje.canal_tipo, exc.detalle,
                )

    # Meta reintenta si no se contesta 200 rápido — se confirma la recepción
    # incluso si más arriba no hubo ningún mensaje de texto que procesar.
    return {"status": "ok"}
