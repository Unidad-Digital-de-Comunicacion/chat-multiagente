"""Cliente HTTP contra el endpoint interno de Core que expone `api_key`/
`webhook_secret` de un canal (`channels.views.InternalCanalConfigView`,
sección 2.1 de docs/CONTEXTO_PROYECTO.md: "Core decide, los demás
ejecutan" — este servicio nunca guarda su propia copia de esas credenciales,
las pide en el momento).

Cada función recibe el `httpx.AsyncClient` compartido de la app como
parámetro explícito (`http_client.get_http_client`, creado una vez en el
`lifespan` de `main.py`) en vez de instanciar uno propio por llamada — el
seam real para los tests es pasar un cliente falso acá, no parchear
`httpx.AsyncClient` (el import global)."""
import httpx

from .config import get_settings
from .schemas import CanalConfig


class CanalNoEncontrado(Exception):
    pass


class CoreNoDisponible(Exception):
    pass


async def _get_canal(client: httpx.AsyncClient, url: str, identificador: str) -> CanalConfig:
    settings = get_settings()
    headers = {"Authorization": f"Service-Token {settings.core_service_token}"}
    try:
        response = await client.get(url, headers=headers)
    except httpx.RequestError as exc:
        raise CoreNoDisponible(f"No se pudo conectar con Core: {exc}") from exc

    if response.status_code == 404:
        raise CanalNoEncontrado(identificador)
    response.raise_for_status()
    data = response.json()
    return CanalConfig(
        organization_id=data["organization_id"],
        tipo=data["tipo"],
        api_key=data["api_key"],
        telefono_id=data.get("telefono_id", ""),
        webhook_secret=data["webhook_secret"],
        activo=data["activo"],
    )


async def obtener_canal(client: httpx.AsyncClient, canal_uuid: str) -> CanalConfig:
    settings = get_settings()
    url = f"{settings.core_base_url}/api/core/internal/canales/{canal_uuid}/"
    return await _get_canal(client, url, canal_uuid)


async def obtener_canal_por_organizacion(client: httpx.AsyncClient, organization_id: int, tipo: str) -> CanalConfig:
    """Meta sólo deja configurar UNA Callback URL por app — Messenger/
    Instagram/WhatsApp de una misma organización pueden llegar a la MISMA
    URL, distinguibles sólo por el `object` del payload (ver `webhooks.py::
    _detectar_tipo_real`). Cuando el tipo real no coincide con el canal de
    la URL que Meta llamó, esto busca el canal "hermano" correcto dentro de
    la misma organización."""
    settings = get_settings()
    url = f"{settings.core_base_url}/api/core/internal/canales/organizacion/{organization_id}/{tipo}/"
    return await _get_canal(client, url, f"org={organization_id} tipo={tipo}")


async def enviar_mensaje_entrante(
    client: httpx.AsyncClient, *, organization_id: int, channel: str, contact_externo_id: str, texto: str,
) -> list[dict]:
    """`POST /api/core/bot/mensaje-entrante/` (sección 4.1 de docs/
    CONTEXTO_PROYECTO.md) — Core decide qué hacer con el mensaje (hoy: crear/
    continuar la `Conversacion` y, si es la primera vez, devolver el mensaje
    de bienvenida) y devuelve `{"acciones": [...]}` para que este servicio
    las ejecute. Si Core no contesta, se devuelve una lista vacía — el
    mensaje ya quedó recibido y logueado del lado de Meta (200), simplemente
    no hay ninguna acción que ejecutar."""
    settings = get_settings()
    url = f"{settings.core_base_url}/api/core/bot/mensaje-entrante/"
    headers = {"Authorization": f"Service-Token {settings.core_service_token}"}
    body = {
        "organization_id": organization_id, "channel": channel,
        "contact_externo_id": contact_externo_id, "texto": texto,
    }
    try:
        response = await client.post(url, headers=headers, json=body)
        response.raise_for_status()
    except httpx.HTTPError:
        return []
    return response.json().get("acciones", [])
