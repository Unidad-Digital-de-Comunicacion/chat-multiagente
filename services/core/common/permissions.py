"""Permisos DRF basados enteramente en el sistema de permisos de Django
(grupos + `Permission`), no en un campo `role` ni en nombres de grupo a
mano: cada vista queda atada al permiso `app_label.accion_modelo` real de su
propio modelo (sección de permisos en docs/CONTEXTO_PROYECTO.md).

Un superusuario real de Django (`is_superuser=True`) sigue pasando siempre
cualquier chequeo (`user.has_perm` lo resuelve así); los usuarios del grupo
"superusuarios" de la plataforma NO son necesariamente `is_superuser=True`
— su alcance real son los permisos que les asigna
`users.group_permissions.GROUP_PERMISSIONS`, para que quede demostrado que
el propio sistema de permisos (no un bypass) es lo que los habilita.
"""
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import DjangoModelPermissions


class StrictDjangoModelPermissions(DjangoModelPermissions):
    """Igual que `DjangoModelPermissions` de DRF, pero además exige el
    permiso `view_<modelo>` para leer (GET/HEAD) — por defecto DRF sólo
    protege las escrituras y deja la lectura abierta a cualquier
    autenticado, que es exactamente lo que no queremos: "que no vean entre
    las opciones funciones que tienen restringidas" aplica también a leer,
    no sólo a escribir."""

    perms_map = {
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": [],
        "HEAD": ["%(app_label)s.view_%(model_name)s"],
        "POST": ["%(app_label)s.add_%(model_name)s"],
        "PUT": ["%(app_label)s.change_%(model_name)s"],
        "PATCH": ["%(app_label)s.change_%(model_name)s"],
        "DELETE": ["%(app_label)s.delete_%(model_name)s"],
    }


def require_perm(request, perm: str) -> None:
    """Para usar dentro de una `@action` u otra vista que no pasa por el
    despacho automático de `StrictDjangoModelPermissions` (porque no mapea
    1 a 1 a add/change/delete/view de un único modelo). `perm` en formato
    "app_label.codename", ej. "menu.change_menuopcion"."""
    if not (request.user and request.user.is_authenticated and request.user.has_perm(perm)):
        raise PermissionDenied(f"Te falta el permiso requerido: {perm}")
