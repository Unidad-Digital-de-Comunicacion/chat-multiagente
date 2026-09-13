"""Registro de canales de mensajería por organización (WhatsApp, Messenger,
Instagram, Webchat): la api key y si el canal está activo o no. Esto es
sólo la CONFIGURACIÓN — según sección 4.4/9 de docs/CONTEXTO_PROYECTO.md,
la conexión real (Embedded Signup, verificación de webhooks, envío de
mensajes) es del Channel Gateway (Fase 3, todavía sin construir), que
además va a guardar el token cifrado en su propia base, no en la de Core.
Mientras tanto esto vive acá para no bloquear la pantalla de configuración
en el Admin Panel — cuando se construya Channel Gateway, migrar estos datos
para allá."""
from django.db import models


class Canal(models.Model):
    class Tipo(models.TextChoices):
        WHATSAPP = "WHATSAPP", "WhatsApp"
        MESSENGER = "MESSENGER", "Messenger"
        INSTAGRAM = "INSTAGRAM", "Instagram"
        WEBCHAT = "WEBCHAT", "Webchat"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="canales",
    )
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    api_key = models.CharField(
        max_length=255, blank=True,
        help_text="Token/credencial del canal. No se devuelve nunca por la API (write-only) — el "
                   "serializer sólo expone si está cargada y sus últimos 4 caracteres.",
    )
    activo = models.BooleanField(
        default=False,
        help_text="Encendido = el canal está habilitado para recibir/enviar mensajes (cuando exista "
                   "Channel Gateway). Apagado no borra la api key, sólo deja el canal fuera de uso.",
    )

    # Resultado del último chequeo de salud contra el servidor remoto real
    # (ver `channels.health.verificar_conexion`) — None en los tres = nunca
    # se chequeó todavía.
    ultimo_chequeo_at = models.DateTimeField(null=True, blank=True)
    ultimo_chequeo_ok = models.BooleanField(null=True, blank=True)
    ultimo_chequeo_detalle = models.CharField(max_length=255, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Canal"
        verbose_name_plural = "Canales"
        ordering = ["tipo"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "tipo"], name="unique_canal_tipo_por_org"),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} — {self.organization.name}"
