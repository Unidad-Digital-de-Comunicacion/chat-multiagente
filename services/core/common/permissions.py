"""Permisos DRF basados enteramente en el sistema de permisos de Django
(grupos + `Permission`), no en un campo `role` ni en nombres de grupo a
mano: cada vista queda atada al permiso `app_label.accion_modelo` real de su
propio modelo (sección de permisos en docs/CONTEXTO_PROYECTO.md).

Un superusuario real de Django (`is_superuser=True`) sigue pasando SIEMPRE
cualquier chequeo de permiso (`user.has_perm`/`require_perm` lo resuelven
así — es un comportamiento de Django, no algo que se pueda apagar acá). Eso
alcanza para la sección "Plataforma" (organizaciones/usuarios/tokens/
estadísticas — recursos que son de toda la plataforma, no de una
organización), pero NO alcanza para bloquearlo de la configuración de UNA
organización en particular (equipos, horarios, menú, mensajes, etiquetas,
canales): ahí el permiso Django ya dio `True`, así que el bloqueo real tiene
que venir de otro lado — `common.viewsets.OrganizationScopedModelViewSet` lo
hace mirando `organization_id` directamente, y `require_organization` de
acá abajo es la misma idea para una vista/acción que arma su propio
queryset a mano en vez de pasar por esa base."""
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission, DjangoModelPermissions


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


class IsPlatformSuperuser(BasePermission):
    """Gate de las vistas de alcance realmente global de la plataforma (ej.
    `organizations.OrganizationViewSet`, que lista/edita TODAS las
    organizaciones, no sólo la del usuario — a diferencia de
    `MyOrganizationView`). No alcanza con los permisos Django estándar
    (`organizations.view_organization`, `users.view_user`, etc.) porque
    `administradores` tiene exactamente esos mismos permisos para su propia
    organización — hace falta un criterio aparte para separar "toda la
    plataforma" de "mi organización", y ese criterio es el mismo que ya usa
    `common.viewsets.OrganizationScopedModelViewSet` para decidir cuándo NO
    filtrar por organización: `is_superuser=True` real de Django y sin
    `organization_id` (una cuenta de plataforma, no la de un tenant)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_superuser and not user.organization_id)


def require_perm(request, perm: str) -> None:
    """Para usar dentro de una `@action` u otra vista que no pasa por el
    despacho automático de `StrictDjangoModelPermissions` (porque no mapea
    1 a 1 a add/change/delete/view de un único modelo). `perm` en formato
    "app_label.codename", ej. "menu.change_menuopcion"."""
    if not (request.user and request.user.is_authenticated and request.user.has_perm(perm)):
        raise PermissionDenied(f"Te falta el permiso requerido: {perm}")


def require_organization(request) -> int:
    """Para una `@action`/vista que arma su propio queryset con
    `request.user.organization_id` a mano en vez de pasar por
    `common.viewsets.OrganizationScopedModelViewSet.get_queryset` (que ya
    hace este mismo chequeo solo). Sin esto, una cuenta de plataforma (sin
    organización — el superusuario real incluido, que `require_perm` no
    bloquea porque Django le da `True` a cualquier permiso) terminaría
    operando en silencio sobre `organization_id=None`: a veces no rompe nada
    visible (sólo deja de tener sentido, ej. una grilla de horario vacía),
    otras veces sí revienta con un `IntegrityError` si el campo no admite
    NULL. Devuelve el id ya validado, para no repetir el chequeo."""
    organization_id = request.user.organization_id
    if not organization_id:
        raise PermissionDenied("Este recurso es de una organización — no aplica a una cuenta de plataforma.")
    return organization_id
