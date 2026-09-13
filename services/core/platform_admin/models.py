"""Modelos de la sección "Plataforma" del Admin Panel (sólo superusuario
real, ver `common.permissions.IsPlatformSuperuser`): tokens compartidos
para que los DEMÁS microservicios de este mismo proyecto (Channel Gateway,
Conversation Engine, Operators Desk, Analytics, Webchat) se autentiquen
contra la API de Core — nunca credenciales de un servicio externo (eso es
`channels.Canal.api_key`, la api key de WhatsApp/Messenger/Instagram, cosa
completamente distinta).

Estos 5 microservicios son hoy stubs de Fase 0 (sólo `/health`, sección 10
de docs/CONTEXTO_PROYECTO.md) — nada consume todavía estos tokens de
verdad, es sólo la configuración, mismo criterio que `channels.Canal` o
`bot_settings.BotMessages` antes de que exista quien los use."""
from django.db import models


class ServiceToken(models.Model):
    class Servicio(models.TextChoices):
        CHANNEL_GATEWAY = "CHANNEL_GATEWAY", "Channel Gateway"
        CONVERSATION_ENGINE = "CONVERSATION_ENGINE", "Conversation Engine"
        OPERATORS_DESK = "OPERATORS_DESK", "Operators Desk"
        ANALYTICS = "ANALYTICS", "Analytics"
        WEBCHAT = "WEBCHAT", "Webchat"

    servicio = models.CharField(max_length=24, choices=Servicio.choices, unique=True)
    token = models.CharField(
        max_length=255, blank=True,
        help_text="Con qué se autentica ese microservicio contra la API de Core. No se devuelve "
                   "nunca por la API (write-only) — el serializer sólo expone si está cargado y sus "
                   "últimos 4 caracteres, igual que `channels.Canal.api_key`.",
    )
    activo = models.BooleanField(
        default=False,
        help_text="Encendido = Core aceptaría este token (cuando el middleware que lo valide "
                   "exista). Apagado no borra el token, sólo lo deja fuera de uso.",
    )
    generado_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Token de servicio interno"
        verbose_name_plural = "Tokens de servicios internos"
        ordering = ["servicio"]

    def __str__(self):
        return f"Token — {self.get_servicio_display()}"
