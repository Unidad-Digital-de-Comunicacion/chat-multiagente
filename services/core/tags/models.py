"""Catálogo de etiquetas de conversación (consigna: "hay etiquetas por
default que son pendiente, asignada, tomada, en proceso, en pausa,
rechazado, resuelto. Además hay etiquetas por cada equipo y el admin puede
agregar/editar/quitar otras etiquetas y definir los colores de las
existentes"). Esta app es sólo la CONFIGURACIÓN del catálogo — quién puede
crear/editar/borrar etiquetas y de qué color son. Aplicarlas a una
conversación, las observaciones de resolución y el chat interno entre
operadores son Fase 4/5 (Conversation Engine / Operators Desk), ver sección
11 de docs/CONTEXTO_PROYECTO.md.
"""
import re

from django.core.exceptions import ValidationError
from django.db import models

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _validar_color(value):
    if not HEX_RE.match(value):
        raise ValidationError("El color debe ser hexadecimal, ej: #3454D1.")


class Etiqueta(models.Model):
    """`organization` es siempre obligatoria (multi-tenant). Dos orígenes
    posibles, ambos automáticos y de sólo lectura para el admin (nunca se
    elige "por equipo o general" a mano al crear una etiqueta):

    - `es_sistema=True`: las 7 etiquetas de estado que existen por default en
      toda organización (una copia por organización, no una fila global,
      para que cada una elija sus propios colores) — identificadas por
      `codigo`, no se pueden borrar ni renombrar, sólo recolorear.
    - `team` cargado: "cada equipo es una etiqueta" — una etiqueta por
      equipo, autogenerada y sincronizada con su nombre (`defaults.
      asegurar_etiquetas_equipo`), tampoco se puede borrar ni renombrar a
      mano (se borra sola en cascada si se borra el equipo).

    Todas las demás etiquetas (las que arma el admin a mano) son generales:
    `team=None`, `es_sistema=False`."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="etiquetas",
    )
    team = models.OneToOneField(
        "teams.Team", on_delete=models.CASCADE, null=True, blank=True, related_name="etiqueta",
        verbose_name="Equipo",
        help_text="Cargado sólo en la etiqueta autogenerada que representa a ese equipo. "
                   "Vacío en toda etiqueta general (de sistema o creada por un Admin).",
    )
    codigo = models.CharField(
        max_length=30, blank=True,
        help_text="Sólo lo usan las 7 etiquetas de sistema, para identificarlas de forma estable.",
    )
    nombre = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default="#6B7280", validators=[_validar_color])
    color_texto = models.CharField(
        max_length=7, default="#FFFFFF", validators=[_validar_color],
        help_text="Color de la fuente sobre `color` — blanco o negro, para que el texto se lea bien "
                   "según qué tan claro/oscuro sea el fondo elegido.",
    )
    es_sistema = models.BooleanField(default=False)
    orden = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Etiqueta"
        verbose_name_plural = "Etiquetas"
        ordering = ["orden", "nombre"]
        constraints = [
            # Sólo para las generales (`team=None`) — Postgres no considera
            # iguales dos NULL para una unique constraint común, así que sin
            # esta condición dos etiquetas generales podrían repetir nombre
            # en la misma organización. Las de equipo ya son únicas por sí
            # solas (`team` es `OneToOneField`).
            models.UniqueConstraint(
                fields=["organization", "nombre"], condition=models.Q(team__isnull=True),
                name="unique_etiqueta_general_nombre_por_org",
            ),
        ]

    def __str__(self):
        return self.nombre

    def clean(self):
        if self.team_id and self.team.organization_id != self.organization_id:
            raise ValidationError({"team": "El equipo debe ser de la misma organización."})
