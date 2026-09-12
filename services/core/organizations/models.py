from django.db import models


class Organization(models.Model):
    """Tenant raíz. Todo el resto de los modelos de negocio cuelga de acá,
    directa o indirectamente, vía `organization` FK (ver sección 1 y 4.1 de
    docs/CONTEXTO_PROYECTO.md)."""

    class Plan(models.TextChoices):
        BASICO = "basico", "Básico"
        PROFESIONAL = "profesional", "Profesional"
        ENTERPRISE = "enterprise", "Enterprise"

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=150, unique=True)
    plan = models.CharField(max_length=20, choices=Plan.choices, default=Plan.BASICO)
    connection_limit = models.PositiveIntegerField(
        default=5,
        help_text="Límite de conexiones simultáneas de operadores (Conversation Engine lo consulta acá).",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]
