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
    """`organization` es siempre obligatoria (multi-tenant). `team` es
    opcional: null = etiqueta general de la organización (incluidas las 7 de
    sistema), cargado = etiqueta propia de ese equipo únicamente.

    `es_sistema=True` marca las 7 etiquetas de estado que existen por
    default en toda organización (una copia por organización, no una fila
    global, para que cada una pueda elegir sus propios colores sin afectar a
    las demás) — se identifican por `codigo` y no se pueden borrar ni
    renombrar, sólo recolorear (ver `EtiquetaSerializer.validate_nombre` y
    `EtiquetaViewSet.perform_destroy`)."""

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="etiquetas",
    )
    team = models.ForeignKey(
        "teams.Team", on_delete=models.CASCADE, null=True, blank=True, related_name="etiquetas",
        verbose_name="Equipo",
        help_text="Vacío = etiqueta general de la organización. Cargado = sólo para ese equipo.",
    )
    codigo = models.CharField(
        max_length=30, blank=True,
        help_text="Sólo lo usan las 7 etiquetas de sistema, para identificarlas de forma estable.",
    )
    nombre = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default="#6B7280", validators=[_validar_color])
    es_sistema = models.BooleanField(default=False)
    orden = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Etiqueta"
        verbose_name_plural = "Etiquetas"
        ordering = ["orden", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "team", "nombre"], name="unique_etiqueta_nombre_por_alcance",
            ),
        ]

    def __str__(self):
        return self.nombre

    def clean(self):
        if self.team_id and self.team.organization_id != self.organization_id:
            raise ValidationError({"team": "El equipo debe ser de la misma organización."})
