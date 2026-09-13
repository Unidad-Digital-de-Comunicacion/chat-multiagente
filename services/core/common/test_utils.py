"""Helpers compartidos por los tests de todas las apps: crear una
organización + un usuario en uno o más grupos y devolver un APIClient ya
autenticado (force_authenticate, sin pasar por el endpoint de login) para no
repetir el mismo boilerplate en cada test file."""
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from organizations.models import Organization
from users.group_permissions import sync_groups
from users.models import User


def make_organization(**kwargs):
    kwargs.setdefault("name", "Organización de prueba")
    kwargs.setdefault("slug", "org-prueba")
    return Organization.objects.create(**kwargs)


def make_user(organization, groups=(), email=None, **kwargs):
    """`groups`: nombres de grupo (ej. `["administradores"]` o
    `["operadores", "analistas_datos"]` — un usuario puede estar en más de
    uno). Se sincronizan los 5 grupos con sus permisos reales en cada
    llamada (idempotente) para que los tests de autorización usen los mismos
    permisos que producción, no una versión simplificada aparte."""
    sync_groups()
    slug_grupos = "-".join(groups) or "sin-grupo"
    email = email or f"{slug_grupos}@{organization.slug}.test"
    user = User.objects.create_user(email=email, password="Contrasena-123", organization=organization, **kwargs)
    if groups:
        user.groups.set(Group.objects.filter(name__in=groups))
    return user


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client
