"""Soft delete de `Organization`/`User` (los únicos dos modelos que lo
necesitan hoy: "eliminar" una organización o un usuario nunca los borra de
la base, sólo los marca — se recuperan desde el Admin Panel o `/admin/`, y
de paso queda un historial de qué existió alguna vez en vez de perderlo).

Ambos modelos ya tenían `is_active` (usado en todo el proyecto como "apagado
pero no borrado" — mismo patrón que `Team.is_active`/`Canal.activo`), así
que un soft delete "de verdad" necesita un campo aparte para poder
distinguir "el Admin lo desactivó a mano" de "está eliminado" y para que las
vistas puedan excluirlo de los listados por default: `deleted_at`
(`None` = no eliminado). Eliminar SIEMPRE apaga `is_active` también (un
eliminado nunca debe poder loguearse ni contar como activo en ningún lado
que sólo mire `is_active`), pero no todo lo que tiene `is_active=False` está
eliminado."""
from django.utils import timezone


def marcar_eliminado(instance) -> None:
    instance.deleted_at = timezone.now()
    instance.is_active = False
    instance.save(update_fields=["deleted_at", "is_active"])


def restaurar_eliminado(instance) -> None:
    instance.deleted_at = None
    instance.is_active = True
    instance.save(update_fields=["deleted_at", "is_active"])
