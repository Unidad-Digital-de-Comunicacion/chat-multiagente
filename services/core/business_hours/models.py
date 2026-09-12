"""Horarios de atención y excepciones de calendario.

Portado de `chatbot/models.py` (HorarioAtencion, DiaExcepcional) del repo
github.com/garzamorada/chatbot, agregando `organization` (sección 5 de
docs/CONTEXTO_PROYECTO.md). `DiaExcepcional.organization=None` es el catálogo
compartido de feriados nacionales (lo carga `sincronizar_feriados`); una
organización puede pisarlo puntualmente con su propia fila para la misma
fecha (ver business_hours.services._rangos_del_dia)."""
from django.db import models


class HorarioAtencion(models.Model):
    class DiaSemana(models.IntegerChoices):
        LUNES = 0, "Lunes"
        MARTES = 1, "Martes"
        MIERCOLES = 2, "Miércoles"
        JUEVES = 3, "Jueves"
        VIERNES = 4, "Viernes"
        SABADO = 5, "Sábado"
        DOMINGO = 6, "Domingo"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="horarios_atencion",
    )
    dia_semana = models.IntegerField(choices=DiaSemana.choices, verbose_name="Día")
    hora_inicio = models.TimeField(verbose_name="Desde")
    hora_fin = models.TimeField(verbose_name="Hasta")
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.get_dia_semana_display()} {self.hora_inicio:%H:%M}-{self.hora_fin:%H:%M}"

    class Meta:
        verbose_name = "Horario de atención"
        verbose_name_plural = "Horarios de atención"
        ordering = ["dia_semana", "hora_inicio"]


class DiaExcepcional(models.Model):
    class Tipo(models.TextChoices):
        FERIADO = "FERIADO", "Feriado — cerrado todo el día"
        ASUETO = "ASUETO", "Asueto — cerrado todo el día"
        HORARIO_REDUCIDO = "HORARIO_REDUCIDO", "Horario reducido"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE,
        null=True, blank=True, related_name="dias_excepcionales",
        help_text="Vacío = catálogo compartido de feriados nacionales.",
    )
    fecha = models.DateField()
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.FERIADO)
    hora_inicio = models.TimeField(null=True, blank=True, help_text="Solo para horario reducido.")
    hora_fin = models.TimeField(null=True, blank=True, help_text="Solo para horario reducido.")
    descripcion = models.CharField(max_length=200, blank=True)
    sincronizado = models.BooleanField(
        default=False, editable=False,
        help_text="True si esta fila la generó la sincronización automática de feriados nacionales.",
    )

    def __str__(self):
        return f"{self.fecha} - {self.get_tipo_display()}"

    class Meta:
        verbose_name = "Día excepcional"
        verbose_name_plural = "Días excepcionales"
        ordering = ["fecha"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "fecha"], name="unique_dia_excepcional_per_org"),
        ]
