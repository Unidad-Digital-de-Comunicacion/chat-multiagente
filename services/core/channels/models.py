"""Registro de canales de mensajería por organización (WhatsApp, Messenger,
Instagram, Webchat): la api key y si el canal está activo o no. Esto es
sólo la CONFIGURACIÓN — según sección 4.4/9 de docs/CONTEXTO_PROYECTO.md,
la conexión real (Embedded Signup, verificación de webhooks, envío de
mensajes) es del Channel Gateway (Fase 3, todavía sin construir), que
además va a guardar el token cifrado en su propia base, no en la de Core.
Mientras tanto esto vive acá para no bloquear la pantalla de configuración
en el Admin Panel — cuando se construya Channel Gateway, migrar estos datos
para allá.

Channel Gateway (Messenger/Instagram, WhatsApp queda para después) ya
existe como servicio real (`services/channel-gateway`) y consume `api_key`
+ `webhook_secret` de acá vía un endpoint interno autenticado con
`ServiceToken` (`platform_admin.service_auth`) — ver
`channels.views.InternalCanalConfigView`. Core sigue siendo quien GENERA y
muestra ambas credenciales (mismo criterio que `platform_admin.
ServiceToken.generar`): Channel Gateway sólo las lee, nunca las crea."""
import uuid as uuid_lib

from django.db import models


class Canal(models.Model):
    class Tipo(models.TextChoices):
        WHATSAPP = "WHATSAPP", "WhatsApp"
        MESSENGER = "MESSENGER", "Messenger"
        INSTAGRAM = "INSTAGRAM", "Instagram"
        WEBCHAT = "WEBCHAT", "Webchat"

    # Los 3 canales que hoy hablan con la Graph API de Meta (webhooks +
    # envío) — Webchat no tiene servidor de terceros que consultar (ver
    # `channels.health`) ni webhook entrante de Meta que verificar.
    TIPOS_CON_WEBHOOK_META = {Tipo.WHATSAPP, Tipo.MESSENGER, Tipo.INSTAGRAM}

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="canales",
    )
    tipo = models.CharField(max_length=12, choices=Tipo.choices)
    uuid = models.UUIDField(
        default=uuid_lib.uuid4, unique=True, editable=False,
        help_text="Identifica este canal en la URL de entrada del webhook (`/webhooks/<tipo>/<uuid>/` "
                   "en Channel Gateway) — no se usa el `id` a propósito para no exponer un correlativo "
                   "adivinable en una URL pública.",
    )
    api_key = models.TextField(
        blank=True,
        help_text="Token/credencial del canal. No se devuelve nunca por la API (write-only) — el "
                   "serializer sólo expone si está cargada y sus últimos 4 caracteres. `TextField` a "
                   "propósito, no `CharField` con un `max_length` — un token de sistema real de "
                   "WhatsApp (Cloud API) puede superar los 255 caracteres que alcanzaban para un "
                   "Page Access Token de Messenger (un `DataError` real lo confirmó en vivo).",
    )
    telefono_id = models.CharField(
        max_length=64, blank=True, verbose_name="Phone Number ID",
        help_text="Sólo WhatsApp: el `phone_number_id` que la Cloud API de Meta necesita en la URL "
                   "de cada envío (`/<phone_number_id>/messages`) — a diferencia de Messenger/"
                   "Instagram, ahí el token solo no alcanza para mandar mensajes. No es secreto (es "
                   "un identificador, no una credencial), así que se devuelve tal cual por la API.",
    )
    waba_id = models.CharField(
        max_length=64, blank=True, verbose_name="WhatsApp Business Account ID",
        help_text="Sólo WhatsApp: identifica la cuenta de WhatsApp Business dueña del número — no "
                   "hace falta para mandar/recibir mensajes (eso usa `telefono_id`), pero lo entrega "
                   "el Embedded Signup y sirve para futuras operaciones a nivel de cuenta (plantillas, "
                   "info del negocio). Tampoco es secreto.",
    )
    webhook_secret = models.CharField(
        max_length=64, blank=True,
        help_text="Generado por Core (nunca por Channel Gateway) al crear el canal — es el "
                   "'verify token' que Meta manda de vuelta al suscribir el webhook y el secreto que "
                   "Channel Gateway usa para confirmar que un webhook entrante corresponde a este "
                   "canal puntual. A diferencia de `api_key`, éste SÍ se devuelve completo por la API: "
                   "el Admin lo tiene que poder copiar para pegarlo en la configuración del webhook.",
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
