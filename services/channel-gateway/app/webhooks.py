"""Recepción de webhooks de Meta para Messenger, Instagram y WhatsApp.

Meta sólo deja configurar UNA Callback URL (+ verify token) por app — no
una por objeto suscripto. En la práctica esto significa que, aunque cada
canal tiene su propia URL acá (`/webhooks/<tipo>/<canal_uuid>/`, el mismo
`uuid` que expone `channels.CanalSerializer.webhook_url` en Core), Meta
puede terminar mandando los tres tipos (Página/Instagram/WhatsApp Business
Account) a la URL que el Admin haya usado para dar de alta la suscripción
en su dashboard — Meta los distingue entre sí por el campo `"object"` del
body (`"page"`/`"instagram"`/`"whatsapp_business_account"`), nunca por la
URL. Por eso el tipo de la URL (`canal_tipo_url`) NUNCA se usa acá para
rechazar un payload — sólo es una pista inicial para encontrar la
organización; el tipo real siempre sale del payload, y si no coincide con
el canal de la URL, se busca el canal "hermano" correcto de la misma
organización (`core_client.obtener_canal_por_organizacion`).

Cada mensaje normalizado se manda a Core (`core_client.
enviar_mensaje_entrante`, sección 4.1 de docs/CONTEXTO_PROYECTO.md) — Core
decide qué hacer (recorrer el árbol de `MenuOpcion`, mandar el mensaje de
bienvenida, etc.) y este servicio sólo ejecuta las `acciones` que devuelve.
Dos tipos de acción: `enviar_texto` (texto plano tal cual) y `mostrar_menu`
(sección 4.1.1 — acá es donde se decide si el canal soporta un widget
nativo de selección; ver `meta_client.enviar_menu_por_canal`)."""
import logging

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from .core_client import (
    CanalNoEncontrado, CoreNoDisponible, enviar_mensaje_entrante, obtener_canal, obtener_canal_por_organizacion,
    obtener_meta_app,
)
from .http_client import get_http_client
from .meta_client import EnvioFallido, enviar_menu_por_canal, enviar_texto_por_canal
from .normalize import normalizar_mensajes
from .schemas import CanalConfig
from .security import verificar_firma, verificar_verify_token

logger = logging.getLogger("channel_gateway.webhooks")

router = APIRouter()

_TIPOS_SOPORTADOS = {"messenger": "MESSENGER", "instagram": "INSTAGRAM", "whatsapp": "WHATSAPP"}

# Valor real de Meta en `payload["object"]` -> nuestro `Canal.Tipo`, y su
# equivalente en minúscula para `normalizar_mensajes` (que espera el mismo
# slug que usan las URLs, "whatsapp"/"messenger"/"instagram").
_OBJETO_A_TIPO = {"page": "MESSENGER", "instagram": "INSTAGRAM", "whatsapp_business_account": "WHATSAPP"}
_TIPO_A_SLUG = {tipo: slug for slug, tipo in _TIPOS_SOPORTADOS.items()}


class WebhookAckResponse(BaseModel):
    status: str


def _tipo_o_404(canal_tipo_url: str) -> None:
    if canal_tipo_url not in _TIPOS_SOPORTADOS:
        raise HTTPException(status_code=404, detail="Canal no soportado (todavía) o inexistente.")


async def _canal_o_404(client: httpx.AsyncClient, canal_uuid: str) -> CanalConfig:
    try:
        return await obtener_canal(client, canal_uuid)
    except CanalNoEncontrado:
        raise HTTPException(status_code=404, detail="No existe ese canal.")
    except CoreNoDisponible as exc:
        raise HTTPException(status_code=503, detail=str(exc))


async def _resolver_canal_real(client: httpx.AsyncClient, canal_url: CanalConfig, tipo_real: str) -> CanalConfig | None:
    """`canal_url` es el canal de la URL que Meta llamó; `tipo_real` es lo
    que el payload realmente dice ser. Si coinciden, no hace falta pedirle
    nada más a Core. Si no, busca el canal hermano de la misma
    organización — `None` si esa organización no tiene ese tipo configurado."""
    if canal_url.tipo == tipo_real:
        return canal_url
    try:
        return await obtener_canal_por_organizacion(client, canal_url.organization_id, tipo_real)
    except CanalNoEncontrado:
        return None
    except CoreNoDisponible:
        return None


# Se registran las dos formas (con y sin `/` final) a propósito: `channels.
# CanalSerializer.get_webhook_url` arma la URL CON `/` final, y es la que
# queda pegada en el dashboard de Meta. Sin este segundo registro, FastAPI
# redirige esa forma a la de sin `/` con un 307 — un bug real en
# producción confirmó que ese redirect le hace perder a Meta el header
# `X-Hub-Signature-256` al reintentar, así que el POST reintentado
# terminaba siempre en 403 "Firma inválida" y el mensaje nunca llegaba a
# procesarse. Registrar ambas formas explícitas evita el redirect por
# completo, no depende de qué variante haya quedado pegada en Meta.
@router.get("/webhooks/{canal_tipo_url}/{canal_uuid}")
@router.get("/webhooks/{canal_tipo_url}/{canal_uuid}/")
async def verificar_suscripcion(
    canal_tipo_url: str, canal_uuid: str, request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> PlainTextResponse:
    """El handshake que Meta hace al dar de alta CADA suscripción (Página/
    Instagram/WhatsApp) — puede pasar varias veces contra esta misma URL si
    el Admin usó la misma para las tres. Meta no manda ninguna pista de
    "para qué tipo" en este handshake (sólo `hub.mode`/`hub.verify_token`/
    `hub.challenge`), así que esto sólo verifica el secreto del canal de la
    URL — no hace falta (ni se puede) resolver el tipo real acá."""
    _tipo_o_404(canal_tipo_url)
    canal = await _canal_o_404(client, canal_uuid)
    params = request.query_params
    if params.get("hub.mode") != "subscribe":
        raise HTTPException(status_code=403, detail="hub.mode inválido.")
    if not verificar_verify_token(params.get("hub.verify_token", ""), canal.webhook_secret):
        raise HTTPException(status_code=403, detail="hub.verify_token inválido.")
    return PlainTextResponse(params.get("hub.challenge", ""))


@router.post("/webhooks/{canal_tipo_url}/{canal_uuid}")
@router.post("/webhooks/{canal_tipo_url}/{canal_uuid}/")
async def recibir_evento(
    canal_tipo_url: str, canal_uuid: str, request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    client: httpx.AsyncClient = Depends(get_http_client),
) -> WebhookAckResponse:
    """Cada mensaje/evento real. Firmado por Meta con `X-Hub-Signature-256`
    sobre el body crudo — se verifica ANTES de tocar el JSON, para no
    procesar nada que no venga realmente de Meta."""
    _tipo_o_404(canal_tipo_url)
    # noqa justificado: hace falta el body CRUDO para verificar la firma
    # HMAC antes de confiar en nada — un body-model de FastAPI ya vendría
    # parseado, sin la representación exacta de bytes que firmó Meta.
    raw_body = await request.body()  # noqa: ASF002
    try:
        meta_app = await obtener_meta_app(client)
    except CoreNoDisponible as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if not verificar_firma(raw_body, x_hub_signature_256, meta_app.app_secret):
        # Nunca el secreto ni la firma completa acá (son credenciales) —
        # sólo lo mínimo para distinguir "no vino el header" de "vino pero
        # no matchea con el secreto configurado para este canal", sin lo
        # cual cada 403 de firma es una caja negra igual de opaca.
        logger.warning(
            "firma inválida canal=%s tiene_header=%s largo_body=%s",
            canal_tipo_url, x_hub_signature_256 is not None, len(raw_body),
        )
        raise HTTPException(status_code=403, detail="Firma inválida.")

    canal_url = await _canal_o_404(client, canal_uuid)
    # noqa justificado: recién acá, DESPUÉS de verificar la firma sobre el
    # body crudo de arriba, es seguro confiar en el JSON — un body-model
    # parsearía antes de esa verificación.
    payload = await request.json()  # noqa: ASF002

    tipo_real = _OBJETO_A_TIPO.get(payload.get("object"))
    if tipo_real is None:
        # Objeto que no reconocemos (Meta manda otros además de mensajería,
        # ej. cambios de perfil) — nada que procesar, pero sigue siendo un
        # 200 real: no es un error, no hay que reintentarlo.
        return WebhookAckResponse(status="ok")

    canal = await _resolver_canal_real(client, canal_url, tipo_real)
    if canal is None:
        # La organización de esta URL no tiene un canal de `tipo_real`
        # configurado — no hay a quién mandarle la api_key/telefono_id.
        logger.warning(
            "webhook de tipo %s sin canal configurado en la organización de %s", tipo_real, canal_uuid,
        )
        return WebhookAckResponse(status="ok")

    mensajes = normalizar_mensajes(_TIPO_A_SLUG[tipo_real], payload)
    for mensaje in mensajes:
        logger.info(
            "mensaje entrante organization_id=%s canal=%s remitente=%s",
            canal.organization_id, mensaje.canal_tipo, mensaje.remitente_id,
        )
        acciones = await enviar_mensaje_entrante(
            client, organization_id=canal.organization_id, channel=canal.tipo,
            contact_externo_id=mensaje.remitente_id, texto=mensaje.texto,
        )
        for accion in acciones:
            tipo_accion = accion.get("tipo")
            try:
                if tipo_accion == "enviar_texto":
                    await enviar_texto_por_canal(client, canal, mensaje.remitente_id, accion["texto"])
                elif tipo_accion == "mostrar_menu":
                    await enviar_menu_por_canal(
                        client, canal, mensaje.remitente_id, accion["texto"],
                        accion.get("encabezado", ""), accion.get("opciones", []),
                    )
            except EnvioFallido as exc:
                # No hay nada mejor que hacer del lado de Meta si esto falla
                # (ej. api_key vencida) — Meta ya recibió su 200 más abajo
                # pase lo que pase acá, así que sólo queda loguearlo.
                logger.warning(
                    "no se pudo ejecutar la acción %s organization_id=%s canal=%s: %s",
                    tipo_accion, canal.organization_id, mensaje.canal_tipo, exc.detalle,
                )

    # Meta reintenta si no se contesta 200 rápido — se confirma la recepción
    # incluso si más arriba no hubo ningún mensaje de texto que procesar.
    return WebhookAckResponse(status="ok")
