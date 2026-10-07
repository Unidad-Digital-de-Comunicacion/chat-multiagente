"""Las 3 etiquetas de sistema "objetivas" (pendiente/asignada/tomada) hasta
ahora eran sólo un dato calculado (`ConversacionSerializer.
get_estado_operativo`, a partir de `estado`/`team`/`operador`) — nunca
quedaban como una fila real de `ConversacionEtiqueta`, así que no había
rastro de CUÁNDO pasó cada paso ni se veían en el historial de auditoría
(`ConversacionHistorialSerializer.etiquetas`). Esto las aplica de verdad,
en los mismos 4 puntos donde cambia el estado: alta de la conversación
(pendiente), derivación automática por el árbol de menú o manual
(asignada), y tomar (tomada) — pedido explícito.

Un solo punto de entrada (no "aplicar asignada acá, tomada allá" a mano en
cada lugar) para que el round-robin de `asignacion.asignar_round_robin`
—que puede dejar team Y operador seteados en el mismo paso— termine
siempre en la etiqueta correcta sin que cada call site tenga que saber
ese detalle."""
from .models import Conversacion, ConversacionEtiqueta


def sincronizar_etiqueta_estado(conversacion: Conversacion, *, aplicada_por=None) -> None:
    from tags.defaults import asegurar_etiquetas_sistema
    from tags.models import Etiqueta

    if conversacion.estado != Conversacion.Estado.ABIERTA:
        # No hay una etiqueta de sistema "cerrada" separada — `cerrada_at`
        # ya es ese registro, y las 3 de acá sólo describen el camino
        # hasta llegar a una conversación tomada, no el cierre en sí.
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
