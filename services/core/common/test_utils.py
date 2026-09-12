"""Helpers compartidos por los tests de todas las apps: crear una
organización + un usuario con rol dado y devolver un APIClient ya
autenticado (force_authenticate, sin pasar por el endpoint de login) para no
repetir el mismo boilerplate en cada test file."""
from rest_framework.test import APIClient

from organizations.models import Organization
from users.models import User


def make_organization(**kwargs):
    kwargs.setdefault("name", "Organización de prueba")
    kwargs.setdefault("slug", "org-prueba")
    return Organization.objects.create(**kwargs)


def make_user(organization, role=User.Role.OPERADOR, email=None, **kwargs):
    email = email or f"{role}@{organization.slug}.test"
    user = User.objects.create_user(email=email, password="Contrasena-123", organization=organization, role=role, **kwargs)
    return user


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client
