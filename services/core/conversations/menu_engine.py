"""Recorrido del árbol de `MenuOpcion` (sección 4.1/5 de docs/
CONTEXTO_PROYECTO.md) — texto numerado plano únicamente, la traducción a
selección nativa por canal (4.1.1) vive en Channel Gateway, no acá; esto
sólo arma el texto neutro y decide a qué nodo se mueve la conversación.

Un mensaje entrante se interpreta como "elegí la opción N" sólo mientras
`Conversacion.menu_finalizado` es `False` — `views.py::MensajeEntranteView`
es quien decide cuándo llamar a `procesar_seleccion` en vez de simplemente
loguear el mensaje para un operador humano."""
from django.utils import timezone

from menu.models import MenuOpcion

from .models import Conversacion


def _texto(texto: str) -> dict | None:
    return {"tipo": "enviar_texto", "texto": texto} if texto else None


def _reemplazar_variables(texto: str, *, nombre: str = "", area: str = "") -> str:
    return texto.replace("{nombre}", nombre or "").replace("{area}", area or "")


def _hijos(organization_id: int, nodo: MenuOpcion | None):
    if nodo is None:
        qs = MenuOpcion.objects.filter(organization_id=organization_id, parent__isnull=True)
    else:
        qs = nodo.hijos.all()
    return list(qs.filter(activo=True).order_by("orden", "texto"))


def render_menu(organization_id: int, nodo: MenuOpcion | None) -> str | None:
    """`None` = no hay nada configurado en ese nivel (menú vacío) — quien
    llama decide qué hacer (típicamente, terminar el modo menú)."""
    hijos = _hijos(organization_id, nodo)
    if not hijos:
        return None

    from bot_settings.models import BotMessages
    from organizations.models import Organization

    bot_messages = BotMessages.para_organizacion(Organization.objects.get(pk=organization_id))
    if nodo is None:
        encabezado = bot_messages.valor_o_default("saludo_inicial")
    else:
        encabezado = _reemplazar_variables(bot_messages.valor_o_default("saludo_area"), area=nodo.texto)

    lineas = [linea for linea in [encabezado] if linea] + [
        f"{i}. {hijo.texto}" for i, hijo in enumerate(hijos, start=1)
    ]
    return "\n".join(lineas)


def _parsear_seleccion(texto: str, cantidad: int) -> int | None:
    try:
        numero = int(texto.strip())
    except (ValueError, AttributeError):
        return None
    return numero if 1 <= numero <= cantidad else None


def procesar_seleccion(conversacion: Conversacion, texto: str) -> list[dict]:
    """Interpreta `texto` como la opción elegida dentro del nivel actual del
    árbol (`conversacion.nodo_menu_actual`) y avanza el estado de la
    conversación en consecuencia. Devuelve la lista de acciones
    `{"tipo": "enviar_texto", ...}` para que Channel Gateway las mande."""
    from bot_settings.models import BotMessages

    organization_id = conversacion.organization_id
    nombre = conversacion.contact.nombre
    hijos = _hijos(organization_id, conversacion.nodo_menu_actual)
    seleccion = _parsear_seleccion(texto, len(hijos))

    if seleccion is None:
        menu_actual = render_menu(organization_id, conversacion.nodo_menu_actual)
        if menu_actual is None:
            # El nivel donde estaba quedó sin opciones activas (se
            # desactivaron todas) — no hay nada más que ofrecer.
            conversacion.menu_finalizado = True
            conversacion.save(update_fields=["menu_finalizado", "updated_at"])
            return []
        return [a for a in [_texto("No entendí esa opción.\n" + menu_actual)] if a]

    elegido = hijos[seleccion - 1]
    bot_messages = BotMessages.para_organizacion(conversacion.contact.organization)

    if elegido.tipo == MenuOpcion.Tipo.SUBMENU:
        siguiente = render_menu(organization_id, elegido)
        conversacion.nodo_menu_actual = elegido
        if siguiente is None:
            conversacion.menu_finalizado = True
        conversacion.save(update_fields=["nodo_menu_actual", "menu_finalizado", "updated_at"])
        return [a for a in [_texto(siguiente)] if a]

    if elegido.tipo == MenuOpcion.Tipo.RESPUESTA:
        acciones = [_texto(_reemplazar_variables(elegido.respuesta_texto, nombre=nombre))]
        menu_actual = render_menu(organization_id, conversacion.nodo_menu_actual)
        if menu_actual:
            acciones.append(_texto(menu_actual))
        else:
            conversacion.menu_finalizado = True
            conversacion.save(update_fields=["menu_finalizado", "updated_at"])
        return [a for a in acciones if a]

    if elegido.tipo == MenuOpcion.Tipo.DERIVACION:
        conversacion.team = elegido.team
        conversacion.menu_finalizado = True
        conversacion.save(update_fields=["team", "menu_finalizado", "updated_at"])
        mensaje = _reemplazar_variables(
            bot_messages.valor_o_default("derivacion_mensaje"), nombre=nombre, area=elegido.texto,
        )
        return [a for a in [_texto(mensaje)] if a]

    if elegido.tipo == MenuOpcion.Tipo.VOLVER:
        nuevo_nodo = conversacion.nodo_menu_actual.parent if conversacion.nodo_menu_actual_id else None
        siguiente = render_menu(organization_id, nuevo_nodo)
        conversacion.nodo_menu_actual = nuevo_nodo
        if siguiente is None:
            conversacion.menu_finalizado = True
        conversacion.save(update_fields=["nodo_menu_actual", "menu_finalizado", "updated_at"])
        return [a for a in [_texto(siguiente)] if a]

    if elegido.tipo == MenuOpcion.Tipo.INICIO:
        siguiente = render_menu(organization_id, None)
        conversacion.nodo_menu_actual = None
        if siguiente is None:
            conversacion.menu_finalizado = True
        conversacion.save(update_fields=["nodo_menu_actual", "menu_finalizado", "updated_at"])
        return [a for a in [_texto(siguiente)] if a]

    if elegido.tipo == MenuOpcion.Tipo.TERMINAR:
        conversacion.menu_finalizado = True
        conversacion.estado = Conversacion.Estado.CERRADA
        conversacion.cerrada_at = timezone.now()
        conversacion.save(update_fields=["menu_finalizado", "estado", "cerrada_at", "updated_at"])
        despedida = _reemplazar_variables(bot_messages.valor_o_default("mensaje_despedida"), nombre=nombre)
        return [a for a in [_texto(despedida)] if a]

    return []
