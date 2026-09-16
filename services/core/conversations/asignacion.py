"""Asignación round-robin de una conversación derivada a un equipo — el
miembro ACTIVO del equipo con MENOS conversaciones abiertas asignadas en
este momento, no un puntero rotativo aparte para "a quién le toca": todo
se recalcula del estado real de `Conversacion` en cada derivación, así que
no hay nada que sincronizar ni que se pueda desincronizar si se borra/edita
un operador o un equipo a mano."""
from django.db.models import Count, Q

from .models import Conversacion


def asignar_round_robin(team):
    """`None` si el equipo no tiene miembros activos — la conversación
    queda igual en la bandeja general sin asignar, ahí cualquier operador
    de la organización la puede tomar a mano."""
    if team is None:
        return None
    return (
        team.members.filter(is_active=True)
        .annotate(
            abiertas=Count(
                "conversaciones_asignadas",
                filter=Q(conversaciones_asignadas__estado=Conversacion.Estado.ABIERTA),
            ),
        )
        .order_by("abiertas", "id")
        .first()
    )
