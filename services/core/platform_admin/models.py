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

from common.encrypted_fields import EncryptedTextField


class ServiceToken(models.Model):
    class Servicio(models.TextChoices):
        CHANNEL_GATEWAY = "CHANNEL_GATEWAY", "Channel Gateway"
        CONVERSATION_ENGINE = "CONVERSATION_ENGINE", "Conversation Engine"
        OPERATORS_DESK = "OPERATORS_DESK", "Operators Desk"
        ANALYTICS = "ANALYTICS", "Analytics"
        WEBCHAT = "WEBCHAT", "Webchat"

    servicio = models.CharField(max_length=24, choices=Servicio.choices, unique=True)
    token = EncryptedTextField(
        blank=True,
        help_text="Con qué se autentica ese microservicio contra la API de Core. Cifrado en reposo "
                   "(`common.encrypted_fields.EncryptedTextField`, 2026-09-20) — antes vivía en "
                   "texto plano. A propósito NO hasheado (irreversible) como una contraseña: este "
                   "mismo valor lo vuelve a mandar CORE hacia ese microservicio en la dirección "
                   "inversa (`conversations.channel_gateway_client`/`conversation_engine_client`, "
                   "`Authorization: Service-Token <este valor>`) — un hash rompería esa dirección, "
                   "sólo sirve para comparar, nunca para reenviar. No se devuelve nunca por la API "
                   "(write-only) — el serializer sólo expone si está cargado y sus últimos 4 "
                   "caracteres, igual que `channels.Canal.api_key`.",
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


class MetaAppConfig(models.Model):
    """`app_id`/`app_secret` de la app de Meta (Facebook Developers) que usa
    TODA la plataforma para WhatsApp/Messenger/Instagram — una sola fila
    (singleton, `obtener()`), no por organización ni por canal (eso es
    `channels.Canal.api_key`, un token de página/negocio distinto por
    canal). Antes vivía sólo en variables de entorno (`META_APP_ID`/
    `META_APP_SECRET`), lo que obligaba a editar el servidor a mano
    (`.env` + reiniciar contenedores) cada vez que hacía falta cambiarla —
    confirmado como un problema real en producción (2026-09-20, ver
    `channels.health`/`channels.embedded_signup`). Ahora es editable desde
    Plataforma por un superusuario, igual que `ServiceToken`. `app_secret`
    es write-only en el serializer, mismo patrón que `channels.Canal.
    api_key` (con reveal completo vía `app_secret_valor`, no sólo preview,
    porque igual que esa es una credencial pegada desde afuera que el
    admin necesita poder verificar entera, no una que generamos nosotros)."""

    app_id = models.CharField(max_length=64, blank=True)
    app_secret = EncryptedTextField(
        blank=True,
        help_text="Cifrado en reposo (`common.encrypted_fields.EncryptedTextField`, 2026-09-20) — "
                   "antes vivía en texto plano en la base.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración de la app de Meta"

    def __str__(self):
        return f"App de Meta — {self.app_id or '(sin configurar)'}"

    @classmethod
    def obtener(cls) -> "MetaAppConfig":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
