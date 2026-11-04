"""Incidentes detectados en los logs / chequeos de salud de TODOS los servicios.

Igual que `authentication.LoginLockout` y `platform_admin`, esto es de
plataforma, no de una organización: un error de Channel Gateway o un servicio
caído afecta a todas a la vez. Se ve sólo desde la sección "Plataforma" del
Admin Panel (`IsPlatformSuperuser`) — la única excepción deliberada al
scoping multi-tenant (ver CLAUDE.md).
"""
from django.conf import settings
from django.db import models

MAX_REQUEST_IDS = 20


class Incidente(models.Model):
    class Tipo(models.TextChoices):
        ERROR = "error", "Error en logs"
        CAIDA = "caida", "Servicio sin responder"
        SEGURIDAD = "seguridad", "Seguridad"

    class Estado(models.TextChoices):
        ABIERTO = "abierto", "Abierto"
        RESUELTO = "resuelto", "Resuelto"

    huella = models.CharField(
        max_length=64, unique=True,
        help_text="Hash de servicio + logger + mensaje normalizado (sin números/ids): la misma falla "
                   "repetida suma ocurrencias en vez de abrir un incidente nuevo cada vez.",
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ABIERTO)
    servicio = models.CharField(max_length=50)
    titulo = models.CharField(max_length=300)
    detalle = models.TextField(blank=True, help_text="Última línea de log que lo disparó (con traceback si hubo).")
    request_ids = models.JSONField(
        default=list, blank=True,
        help_text=f"Últimos {MAX_REQUEST_IDS} request_id afectados — para seguir el pedido en los logs de todos "
                   "los servicios desde el panel.",
    )
    ocurrencias = models.PositiveIntegerField(default=0)
    primera_vez = models.DateTimeField()
    ultima_vez = models.DateTimeField()
    notificado_at = models.DateTimeField(null=True, blank=True)
    ocurrencias_notificadas = models.PositiveIntegerField(default=0)
    resuelto_at = models.DateTimeField(null=True, blank=True)
    resuelto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="Vacío si se resolvió solo (ej. un servicio caído que volvió a responder).",
    )

    class Meta:
        ordering = ["-ultima_vez"]
        indexes = [models.Index(fields=["estado", "-ultima_vez"])]

    def __str__(self):
        return f"[{self.get_estado_display()}] {self.titulo}"


class CursorLog(models.Model):
    """Hasta dónde ya leyó el detector cada archivo de log (byte offset +
    inode, para detectar la rotación)."""

    archivo = models.CharField(max_length=500, unique=True)
    inode = models.BigIntegerField(default=0)
    offset = models.BigIntegerField(default=0)
    actualizado_at = models.DateTimeField(auto_now=True)


class ChequeoSalud(models.Model):
    """Último resultado de cada chequeo HTTP (`settings.MONITOREO_CHEQUEOS`)."""

    nombre = models.CharField(max_length=100, unique=True)
    url = models.CharField(max_length=500)
    ok = models.BooleanField(null=True)
    fallos_consecutivos = models.PositiveIntegerField(default=0)
    ultimo_detalle = models.CharField(max_length=500, blank=True)
    ultimo_chequeo_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["nombre"]
