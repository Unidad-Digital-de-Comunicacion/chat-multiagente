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
        default=0,
        verbose_name="Límite de operadores concurrentes",
        help_text="Máximo de operadores conectados/tomando conversaciones a la vez (Conversation "
                   "Engine lo va a consultar acá, Fase 4 — todavía no implementado). 0 = sin límite.",
    )
    user_limit = models.PositiveIntegerField(
        default=0,
        verbose_name="Límite de usuarios",
        help_text="Máximo de usuarios (de cualquier grupo) que puede tener la organización. 0 = sin "
                   "límite. Es sólo el tope configurado: todavía no se aplica al crear un usuario.",
    )
    monthly_conversation_limit = models.PositiveIntegerField(
        default=0,
        verbose_name="Límite de conversaciones mensuales",
        help_text="Máximo de conversaciones nuevas por mes calendario. 0 = sin límite. El conteo real "
                   "es del Conversation Engine, Fase 4 — acá sólo se guarda el tope configurado.",
    )
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Soft delete: null = no está eliminada. Se marca (nunca se borra la fila, ni la "
                   "de la organización ni las de sus usuarios) al eliminarla desde la sección "
                   "\"Plataforma\" — recuperable con la action `restaurar` de "
                   "`PlatformOrganizationViewSet`, o desde /admin/ (`common.soft_delete`).",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]
