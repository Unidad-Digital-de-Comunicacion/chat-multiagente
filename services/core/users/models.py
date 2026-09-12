from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """Usuario de la plataforma. `email` es el identificador de login (no
    `username`: en un SaaS multi-tenant es más natural que dos organizaciones
    distintas no choquen por nombre de usuario). `organization` es null sólo
    para el superusuario de plataforma; todo usuario de negocio pertenece a
    una y sólo una organización."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        DIFUSION = "difusion", "Difusión"
        OPERADOR = "operador", "Operador"
        DATA_MANAGER = "data_manager", "Data Manager"

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE,
        null=True, blank=True, related_name="users",
    )
    role = models.CharField(max_length=20, choices=Role.choices, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    class Meta:
        ordering = ["email"]
