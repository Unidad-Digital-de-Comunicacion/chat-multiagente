"""Recorrido del árbol de `MenuOpcion` (sección 4.1/4.1.1/5 de docs/
CONTEXTO_PROYECTO.md). Un menú se devuelve como acción `mostrar_menu` con
tres partes — `texto` (encabezado + listado numerado, el fallback universal),
`encabezado` (sólo el saludo, sin numerar — lo que un widget nativo como
`interactive.type=list/button` de WhatsApp muestra como cuerpo, porque el
propio widget ya lista las opciones) y `opciones: [{id, titulo}]` (lista
estructurada, `id` es la posición 1-based como string). **Core decide el
contenido, nunca el formato de UI del canal** — armar el widget nativo o
caer al texto plano numerado es decisión de Channel Gateway, no de acá
(sección 2.1). El `id` de cada opción es a propósito el mismo string que
`_parsear_seleccion` ya acepta escrito a mano, así que tanto tipear "2"
como tocar una fila/botón nativo producen el mismo `texto` de vuelta acá.

Un mensaje entrante se interpreta como "elegí la opción N" sólo mientras
`Conversacion.menu_finalizado` es `False` — `views.py::MensajeEntranteView`
es quien decide cuándo llamar a `procesar_seleccion` en vez de simplemente
loguear el mensaje para un operador humano."""
from dataclasses import dataclass

from django.utils import timezone

from menu.models import MenuOpcion

from .etiqueta_sistema import sincronizar_etiqueta_equipo, sincronizar_etiqueta_estado
from .models import Conversacion


@dataclass(frozen=True)
class MenuRenderizado:
    texto: str
    encabezado: str
    opciones: list[dict]


def _texto(texto: str) -> dict | None:
    return {"tipo": "enviar_texto", "texto": texto} if texto else None


def accion_menu(renderizado: MenuRenderizado | None) -> dict | None:
    if renderizado is None:
        return None
    return {
        "tipo": "mostrar_menu", "texto": renderizado.texto,
        "encabezado": renderizado.encabezado, "opciones": renderizado.opciones,
    }


def _reemplazar_variables(texto: str, *, nombre: str = "", area: str = "") -> str:
    return texto.replace("{nombre}", nombre or "").replace("{area}", area or "")


def _hijos(organization_id: int, nodo: MenuOpcion | None):
    if nodo is None:
        qs = MenuOpcion.objects.filter(organization_id=organization_id, parent__isnull=True)
    else:
        qs = nodo.hijos.all()
    return list(qs.filter(activo=True).order_by("orden", "texto"))


def render_menu(organization_id: int, nodo: MenuOpcion | None) -> MenuRenderizado | None:
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

    opciones = [{"id": str(i), "titulo": hijo.texto} for i, hijo in enumerate(hijos, start=1)]
    lineas = [linea for linea in [encabezado] if linea] + [
        f"{o['id']}. {o['titulo']}" for o in opciones
    ]
    return MenuRenderizado(texto="\n".join(lineas), encabezado=encabezado, opciones=opciones)


def _parsear_seleccion(texto: str, cantidad: int) -> int | None:
    try:
        numero = int(texto.strip())
    except (ValueError, AttributeError):
        return None
    return numero if 1 <= numero <= cantidad else None


def procesar_seleccion(conversacion: Conversacion, texto: str) -> list[dict]:
    """Interpreta `texto` como la opción elegida dentro del nivel actual del
    árbol (`conversacion.nodo_menu_actual`) y avanza el estado de la
    conversación en consecuencia. `texto` puede venir de que el contacto
    haya escrito el número a mano, o de que haya tocado una fila/botón
    nativo — ver el docstring del módulo, el `id` de cada opción es el
    mismo formato en los dos casos."""
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
        aviso = accion_menu(menu_actual)
        aviso["texto"] = "No entendí esa opción.\n" + aviso["texto"]
        return [aviso]

    elegido = hijos[seleccion - 1]
    bot_messages = BotMessages.para_organizacion(conversacion.contact.organization)

    # La etiqueta de equipo marca el ÁREA por la que el contacto está
    # navegando, no si ya llegó a un operador — por eso se sincroniza acá,
    # para CUALQUIER opción que tenga un equipo cargado (`team` es un campo
    # libre en todo tipo de `MenuOpcion`, no sólo Derivación: un Admin puede
    # cargarlo en un SUBMENU para marcar "esto es el área de Soporte" desde
    # que se entra, aunque todavía falten pasos para derivar). Si la opción
    # elegida no tiene equipo (Volver/Inicio/Terminar, o un submenú/
    # respuesta sin área asociada), no se toca la etiqueta de equipo que ya
    # hubiera — sólo cambia cuando hay un equipo nuevo al que cambiar.
    if elegido.team_id:
        sincronizar_etiqueta_equipo(conversacion, elegido.team_id)

    if elegido.tipo == MenuOpcion.Tipo.SUBMENU:
        siguiente = render_menu(organization_id, elegido)
        conversacion.nodo_menu_actual = elegido
        if siguiente is None:
            conversacion.menu_finalizado = True
        conversacion.save(update_fields=["nodo_menu_actual", "menu_finalizado", "updated_at"])
        return [a for a in [accion_menu(siguiente)] if a]

    if elegido.tipo == MenuOpcion.Tipo.RESPUESTA:
        acciones = [_texto(_reemplazar_variables(elegido.respuesta_texto, nombre=nombre))]
        menu_actual = render_menu(organization_id, conversacion.nodo_menu_actual)
        if menu_actual:
            acciones.append(accion_menu(menu_actual))
        else:
            conversacion.menu_finalizado = True
            conversacion.save(update_fields=["menu_finalizado", "updated_at"])
        return [a for a in acciones if a]

    if elegido.tipo == MenuOpcion.Tipo.DERIVACION:
        # Queda en la bandeja general del equipo, no asignada a un
        # operador puntual — la asignación es al EQUIPO hasta que alguien
        # la toma de verdad (`ConversacionViewSet.tomar`), pedido
        # explícito (antes el round-robin de `asignacion.
        # asignar_round_robin` elegía un operador acá mismo, lo que podía
        # recaer en cualquier miembro del equipo, incluido un admin
        # agregado por error, y la saltaba directo a "tomada" sin que
        # nadie la haya tomado en los hechos). La etiqueta de equipo ya
        # quedó sincronizada arriba (toda Derivación tiene `team` cargado).
        conversacion.team = elegido.team
        conversacion.menu_finalizado = True
        conversacion.derivada_at = timezone.now()
        conversacion.save(update_fields=["team", "menu_finalizado", "derivada_at", "updated_at"])
        sincronizar_etiqueta_estado(conversacion)
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
        return [a for a in [accion_menu(siguiente)] if a]

    if elegido.tipo == MenuOpcion.Tipo.INICIO:
        siguiente = render_menu(organization_id, None)
        conversacion.nodo_menu_actual = None
        if siguiente is None:
            conversacion.menu_finalizado = True
        conversacion.save(update_fields=["nodo_menu_actual", "menu_finalizado", "updated_at"])
        return [a for a in [accion_menu(siguiente)] if a]

    if elegido.tipo == MenuOpcion.Tipo.TERMINAR:
        conversacion.menu_finalizado = True
        conversacion.estado = Conversacion.Estado.CERRADA
        conversacion.cerrada_at = timezone.now()
        conversacion.save(update_fields=["menu_finalizado", "estado", "cerrada_at", "updated_at"])
        despedida = _reemplazar_variables(bot_messages.valor_o_default("mensaje_despedida"), nombre=nombre)
        return [a for a in [_texto(despedida)] if a]

    return []
