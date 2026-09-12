from django.conf import settings
from django.db import models


class Team(models.Model):
    """Equipo de una organización. Es el destino de las derivaciones del
    árbol de menú (menu.MenuOpcion tipo DERIVACION) y de la asignación
    round-robin del Conversation Engine (Fase 4)."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="teams",
    )
    name = models.CharField(max_length=150)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name="teams", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="unique_team_name_per_org"),
        ]
