"""Árbol de menú del bot. Portado de `chatbot/models.py::MenuOpcion` del repo
github.com/garzamorada/chatbot (mismo árbol recursivo `parent`/`hijos` y
autogeneración de `slug`), adaptado a multi-tenant (sección 4.1 y 5 de
docs/CONTEXTO_PROYECTO.md):

- `organization` FK obligatoria; `slug` único por organización (no global).
- `DERIVACION` pasa a ser un tipo de nodo explícito del árbol con FK
  obligatoria a `Team` (en el original era una opción de navegación
  auto-agregada que aplicaba una etiqueta de texto en chatealo).
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class MenuOpcion(models.Model):
    class Tipo(models.TextChoices):
        SUBMENU = "SUBMENU", "Menú — agrupa otras opciones"
        RESPUESTA = "RESPUESTA", "Respuesta directa — el bot contesta un texto"
        DERIVACION = "DERIVACION", "Derivación — transfiere a un equipo"
        VOLVER = "VOLVER", "Volver al menú anterior"
        INICIO = "INICIO", "Volver al menú principal"
        TERMINAR = "TERMINAR", "Terminar la conversación"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="menu_opciones",
    )
    texto = models.CharField(max_length=200, verbose_name="Texto de la opción")
    slug = models.SlugField(
        max_length=100, blank=True,
        help_text="Se autogenera del texto si se deja vacío. Único dentro de la organización.",
    )
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True,
        related_name="hijos", verbose_name="Dentro del menú",
    )
    orden = models.IntegerField(default=0, verbose_name="Orden")
    tipo = models.CharField(max_length=12, choices=Tipo.choices, default=Tipo.SUBMENU)

    respuesta_texto = models.TextField(
        blank=True, verbose_name="Texto de respuesta",
        help_text="Sólo tipo Respuesta: el texto que el bot devuelve al elegir esta opción.",
    )
    team = models.ForeignKey(
        "teams.Team", on_delete=models.PROTECT, null=True, blank=True, related_name="menu_derivaciones",
        verbose_name="Equipo al que deriva",
        help_text="Obligatorio para tipo Derivación.",
    )

    activo = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.tipo == self.Tipo.DERIVACION and not self.team_id:
            raise ValidationError({"team": "Una opción de tipo Derivación necesita un equipo."})
        if self.tipo == self.Tipo.RESPUESTA and not self.respuesta_texto.strip():
            raise ValidationError({"respuesta_texto": "Una opción de tipo Respuesta necesita un texto."})
        if self.parent_id and self.parent.organization_id != self.organization_id:
            raise ValidationError({"parent": "El menú padre debe ser de la misma organización."})
        if self.team_id and self.team.organization_id != self.organization_id:
            raise ValidationError({"team": "El equipo debe ser de la misma organización."})

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.texto)[:90] or "opcion"
            slug = base_slug
            n = 1
            while (
                MenuOpcion.objects.filter(organization_id=self.organization_id, slug=slug)
                .exclude(pk=self.pk)
                .exists()
            ):
                slug = f"{base_slug}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.texto

    class Meta:
        verbose_name = "Opción de menú"
        verbose_name_plural = "Opciones de menú"
        ordering = ["orden", "texto"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "slug"], name="unique_menu_slug_per_org"),
        ]
