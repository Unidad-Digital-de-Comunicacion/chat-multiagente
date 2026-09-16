"""Fuente única de verdad de qué puede hacer cada uno de los 5 grupos de la
plataforma (permisos Django estándar: add_/change_/delete_/view_<modelo>).
La usan tanto el management command `setup_groups` (producción/dev) como los
tests (`common.test_utils`), para no tener la relación grupo→permiso
duplicada en dos lugares.

Un usuario puede pertenecer a más de un grupo a la vez (M2M nativo de
`PermissionsMixin.groups`); sus permisos efectivos son la unión de los de
todos sus grupos (`user.has_perm(...)` ya lo resuelve así).

- superusuarios: staff (acceden a /admin/ y a la sección "Plataforma" del
  Admin Panel — ver `common.permissions.IsPlatformSuperuser`), gestionan
  organizaciones (incl. sus límites de uso) y las cuentas de cualquier
  organización, los tokens de comunicación entre los propios microservicios
  del proyecto, y ven estadísticas/salud generales del sistema. No son
  necesariamente `is_superuser=True` de Django para estos permisos Django
  estándar — pero las vistas de alcance realmente global (que devuelven
  datos de TODAS las organizaciones a la vez, no sólo la propia) exigen
  además `is_superuser=True` real (`IsPlatformSuperuser`), porque
  `organizations.view_organization`/`change_organization` y
  `users.view_user`/etc. son los MISMOS permisos que ya tiene
  `administradores` para su propia organización — el permiso Django por sí
  solo no alcanza para distinguir "toda la plataforma" de "mi organización".
- administradores: sólo desde el Admin Panel (React); gestionan usuarios,
  equipos y permisos (grupos) de su propia organización, configuran el
  chatbot (menú + horarios + mensajes predeterminados), el catálogo de
  etiquetas de conversación (por organización y por equipo) y la api key/
  estado de cada canal de mensajería (WhatsApp/Messenger/Instagram/Webchat).
- encargados_difusion / analistas_datos: NINGÚN permiso sobre Core — para
  estos dos grupos, Core es sólo la API de autenticación (login, recuperar
  usuario/contraseña por DNI, "mi perfil") que van a usar sus propios
  microservicios/paneles cuando existan (Analytics, campañas de difusión —
  Fase 7/9, ver sección 11 de docs/CONTEXTO_PROYECTO.md); no tienen ninguna
  pantalla de configuración en el Admin Panel de Core.
- operadores: ve y gestiona `conversations.Conversacion` de su propia
  organización (bandeja sin asignar, tomar/responder/cerrar una
  conversación) desde `frontend/operators-desk-web` — versión MVP de lo que
  documentaba la sección 11 como Operators Desk Service (Fase 4/5), armada
  directo contra Core en vez de como un BFF aparte (ver "Cola de mensajes"
  en docs/CONTEXTO_PROYECTO.md). Sin permisos de administración de ningún
  tipo (usuarios/equipos/menú/etc.) — eso sigue siendo sólo de
  `administradores`.
"""
from typing import Final

# `Final` (en vez de sólo `dict[str, list[str]]`) para no perder el
# conjunto de claves conocido del literal de abajo.
GROUP_PERMISSIONS: Final[dict[str, list[str]]] = {
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
        "channels.view_canal",
        "channels.change_canal",
        "conversations.view_conversacion",
        "conversations.change_conversacion",
    ],
    "encargados_difusion": [],
    "analistas_datos": [],
    "operadores": [
        "conversations.view_conversacion",
        "conversations.change_conversacion",
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
