"""Dos ejes de etiqueta de sistema, independientes entre sí y cada uno
mutuamente excluyente sólo contra sí mismo (pedido explícito):

- **Estado** (`sincronizar_etiqueta_estado`): pendiente/asignada/tomada
  (más en_proceso/en_pausa/rechazado/resuelto, elegidas a mano — ver
  `ConversacionViewSet.etiquetas`), generales e iguales en toda
  organización (`es_sistema=True`). Hasta ahora eran sólo un dato
  calculado (`ConversacionSerializer.get_estado_operativo`, a partir de
  `estado`/`team`/`operador`) — nunca quedaban como una fila real de
  `ConversacionEtiqueta`, así que no había rastro de CUÁNDO pasó cada
  paso ni se veían en el historial de auditoría
  (`ConversacionHistorialSerializer.etiquetas`). Esto las aplica de
  verdad, en los 3 puntos donde cambia el estado operativo: alta de la
  conversación (pendiente), derivación — automática por el árbol de menú
  o manual (asignada) — y tomar (tomada). YA NO hay asignación automática
  de operador en la derivación (ver `menu_engine.procesar_seleccion`), así
  que una conversación recién derivada siempre queda en "asignada" (al
  equipo), nunca salta directo a "tomada" sin que un operador la tome de
  verdad con `ConversacionViewSet.tomar`.
- **Equipo** (`sincronizar_etiqueta_equipo`): "cada equipo es una
  etiqueta" (`tags.defaults.asegurar_etiquetas_equipo`). Marca el ÁREA por
  la que el contacto está navegando, no si ya llegó a un operador —
  `menu_engine.procesar_seleccion` la sincroniza para CUALQUIER opción de
  menú elegida que tenga un equipo cargado (`MenuOpcion.team` es un campo
  libre en todo tipo de nodo, no sólo Derivación: un Admin puede cargarlo
  en un SUBMENU para marcar "esto es el área de Soporte" desde que se
  entra, sin esperar a que el árbol llegue a derivar), y
  `ConversacionViewSet.derivar` al derivar a mano a otro equipo — nunca al
  tomar/cerrar (no cambian de área). Por eso recibe el equipo explícito
  por parámetro en vez de leer `conversacion.team` — las dos cosas pueden
  ir desacopladas: el contacto puede estar "en el área de Soporte" (la
  etiqueta ya cambió) sin que la conversación todavía esté derivada de
  verdad (`conversacion.team` sigue en lo que estaba, o vacío). Reemplaza
  cualquier etiqueta de equipo anterior (una sola a la vez), pero no toca
  ni las de estado ni las generales/personalizadas que el admin u operador
  hayan agregado a mano — esas son acumulativas, quedan hasta que alguien
  las saca explícitamente.

Un solo punto de entrada por eje (no "aplicar asignada acá, tomada allá"
a mano en cada lugar) para que cada call site no tenga que repetir el
criterio de exclusión mutua."""
from .models import Conversacion, ConversacionEtiqueta


def sincronizar_etiqueta_estado(conversacion: Conversacion, *, aplicada_por=None) -> None:
    from tags.defaults import asegurar_etiquetas_sistema
    from tags.models import Etiqueta

    if conversacion.estado != Conversacion.Estado.ABIERTA:
        # No hay una etiqueta de sistema "cerrada" separada — `cerrada_at`
        # ya es ese registro, y las de acá sólo describen el camino hasta
        # llegar a una conversación tomada, no el cierre en sí.
        return

    if conversacion.operador_id:
        codigo = "tomada"
    elif conversacion.team_id:
        codigo = "asignada"
    else:
        codigo = "pendiente"

    asegurar_etiquetas_sistema(conversacion.organization_id)
    etiqueta = Etiqueta.objects.get(organization_id=conversacion.organization_id, codigo=codigo, es_sistema=True)

    # Mutuamente excluyentes entre sí, mismo criterio que `ConversacionViewSet.
    # etiquetas` ya aplica para cualquier etiqueta de sistema elegida a mano.
    conversacion.etiquetas_aplicadas.filter(etiqueta__es_sistema=True).exclude(etiqueta=etiqueta).delete()
    ConversacionEtiqueta.objects.update_or_create(
        conversacion=conversacion, etiqueta=etiqueta, defaults={"aplicada_por": aplicada_por},
    )


def sincronizar_etiqueta_equipo(conversacion: Conversacion, team_id, *, aplicada_por=None) -> None:
    """`team_id` es explícito (no se lee de `conversacion.team`) — quien
    llama decide de qué equipo es la etiqueta, porque puede ser el del
    nodo de menú recién elegido sin que `conversacion.team` haya
    cambiado todavía (ver docstring del módulo)."""
    from tags.defaults import asegurar_etiquetas_equipo
    from tags.models import Etiqueta

    # Sólo entre las etiquetas de equipo entre sí (eje independiente del de
    # estado).
    conversacion.etiquetas_aplicadas.filter(etiqueta__team__isnull=False).exclude(
        etiqueta__team_id=team_id,
    ).delete()
    if team_id is None:
        return

    asegurar_etiquetas_equipo(conversacion.organization_id)
    etiqueta = Etiqueta.objects.get(organization_id=conversacion.organization_id, team_id=team_id)
    ConversacionEtiqueta.objects.update_or_create(
        conversacion=conversacion, etiqueta=etiqueta, defaults={"aplicada_por": aplicada_por},
    )
