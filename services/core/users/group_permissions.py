"""Fuente única de verdad de qué puede hacer cada uno de los 5 grupos de la
plataforma (permisos Django estándar: add_/change_/delete_/view_<modelo>).
La usan tanto el management command `setup_groups` (producción/dev) como los
tests (`common.test_utils`), para no tener la relación grupo→permiso
duplicada en dos lugares.

Un usuario puede pertenecer a más de un grupo a la vez (M2M nativo de
`PermissionsMixin.groups`); sus permisos efectivos son la unión de los de
todos sus grupos (`user.has_perm(...)` ya lo resuelve así).

- superusuarios: staff (acceden a /admin/), gestionan organizaciones y las
  cuentas Admin de cada una. No son necesariamente `is_superuser=True` de
  Django — el alcance real lo dan estos permisos, no un bypass total.
- administradores: sólo desde el Admin Panel (React); gestionan usuarios,
  equipos y permisos (grupos) de su propia organización, y configuran el
  chatbot (menú + horarios + mensajes predeterminados) y el catálogo de
  etiquetas de conversación (por organización y por equipo).
- encargados_difusion / analistas_datos: grupos creados de antemano; sus
  funciones (campañas de difusión; reportes de conversaciones/agentes/
  contactos) dependen de apps que todavía no existen (Fase 7+/9) — quedan
  sin permisos reales hasta que se construyan esas vistas.
- operadores: de sólo lectura sobre equipos, horario hábil y el catálogo de
  etiquetas por ahora — aplicar/quitar etiquetas de una conversación, las
  observaciones de resolución y el chat interno entre operadores son
  Fase 4/5, todavía no implementadas (ver sección 11 de
  docs/CONTEXTO_PROYECTO.md).
"""

GROUP_PERMISSIONS: dict[str, list[str]] = {
    "superusuarios": [
        "organizations.add_organization",
        "organizations.change_organization",
        "organizations.view_organization",
        "users.add_user",
        "users.change_user",
        "users.view_user",
        "auth.view_group",
        "authentication.view_loginlockout",
        "authentication.change_loginlockout",
        "authentication.delete_loginlockout",
    ],
    "administradores": [
        "organizations.view_organization",
        "organizations.change_organization",
        "users.add_user",
        "users.change_user",
        "users.delete_user",
        "users.view_user",
        "auth.view_group",
        "teams.add_team",
        "teams.change_team",
        "teams.delete_team",
        "teams.view_team",
        "menu.add_menuopcion",
        "menu.change_menuopcion",
        "menu.delete_menuopcion",
        "menu.view_menuopcion",
        "business_hours.add_horarioatencion",
        "business_hours.change_horarioatencion",
        "business_hours.delete_horarioatencion",
        "business_hours.view_horarioatencion",
        "business_hours.add_diaexcepcional",
        "business_hours.change_diaexcepcional",
        "business_hours.delete_diaexcepcional",
        "business_hours.view_diaexcepcional",
        "bot_settings.view_botmessages",
        "bot_settings.change_botmessages",
        "tags.add_etiqueta",
        "tags.change_etiqueta",
        "tags.delete_etiqueta",
        "tags.view_etiqueta",
    ],
    "encargados_difusion": [],
    "analistas_datos": [],
    "operadores": [
        "organizations.view_organization",
        "teams.view_team",
        "business_hours.view_horarioatencion",
        "tags.view_etiqueta",
    ],
}

# Grupos que un Admin de organización NO puede asignar a otros usuarios desde
# el Admin Panel (son de alcance de plataforma, se otorgan desde /admin/).
GRUPOS_RESERVADOS_A_PLATAFORMA = {"superusuarios"}


def sync_groups():
    """Crea/actualiza los 5 grupos con exactamente los permisos de
    GROUP_PERMISSIONS (idempotente — correrlo de nuevo también saca
    permisos que se hayan sacado de la lista). Requiere que los permisos
    "de fábrica" de cada modelo ya existan (los crea Django en `migrate`)."""
    from django.contrib.auth.models import Group, Permission

    grupos = {}
    for nombre, perm_strings in GROUP_PERMISSIONS.items():
        grupo, _ = Group.objects.get_or_create(name=nombre)
        permisos = []
        for perm_string in perm_strings:
            app_label, codename = perm_string.split(".", 1)
            permisos.append(Permission.objects.get(content_type__app_label=app_label, codename=codename))
        grupo.permissions.set(permisos)
        grupos[nombre] = grupo
    return grupos
