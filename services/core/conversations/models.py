"""Versión MVP de `Conversacion`/`ConversacionLog`/`Contact` (sección 4.1 de
docs/CONTEXTO_PROYECTO.md) — recortada a propósito para tener la "bandeja sin
asignar" funcionando de punta a punta: recibe el mensaje entrante (`POST /api/
core/bot/mensaje-entrante/`, ver `views.py::MensajeEntranteView`), recorre el
árbol de `MenuOpcion` mientras el contacto sigue eligiendo opciones (ver
`menu_engine.py`), y una vez que sale del menú (derivación/fin de menú/
opción "Terminar") queda esperando a que un operador la tome desde
`ConversacionViewSet`.

Lo que NO tiene todavía (a propósito, no es un olvido): selección nativa
por canal (sección 4.1.1 — WhatsApp/Messenger tienen widgets de lista/
botones, acá todo es texto numerado plano), ni el `OperatorSession`/
asignación round-robin real de Conversation Engine (Fase 4) — la
derivación por `team` sólo queda guardada en la conversación, más adelante
sirve para filtrar la bandeja por equipo."""
from django.db import models

from channels.models import Canal


class Contact(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="contactos",
    )
    canal = models.CharField(max_length=12, choices=Canal.Tipo.choices)
    identificador_externo = models.CharField(
        max_length=64,
        help_text="Número de teléfono en WhatsApp, PSID en Messenger, IGSID en Instagram.",
    )
    nombre = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Contacto"
        verbose_name_plural = "Contactos"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "canal", "identificador_externo"], name="unique_contact_por_canal",
            ),
        ]

    def __str__(self):
        return self.nombre or self.identificador_externo


class Conversacion(models.Model):
    class Estado(models.TextChoices):
        ABIERTA = "ABIERTA", "Abierta"
        CERRADA = "CERRADA", "Cerrada"

    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="conversaciones",
    )
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name="conversaciones")
    canal = models.CharField(max_length=12, choices=Canal.Tipo.choices)
    operador = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="conversaciones_asignadas",
        help_text="Vacío = en la bandeja sin asignar, cualquier operador de la organización la puede tomar.",
    )
    bloqueada_hasta = models.DateTimeField(
        null=True, blank=True,
        help_text="Mientras esté en el futuro, sólo `operador` puede seguir operando esta "
                   "conversación (tomarla de nuevo, responder) — otro operador no puede "
                   "reclamarla hasta que venza. Se pone en +2 minutos al asignarla (por round-robin "
                   "o a mano) y se renueva en cada `tomar`/`responder`; una vez vencida, cualquier "
                   "operador la puede reclamar (ver `ConversacionViewSet.tomar`).",
    )
    team = models.ForeignKey(
        "teams.Team", on_delete=models.SET_NULL, null=True, blank=True, related_name="conversaciones",
        help_text="Se completa al elegir una opción de menú tipo Derivación — dispara la asignación "
                   "round-robin dentro del equipo (`conversations.asignacion.asignar_round_robin`).",
    )
    nodo_menu_actual = models.ForeignKey(
        "menu.MenuOpcion", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        help_text="En qué nodo del árbol está esta conversación mientras sigue en modo bot — "
                   "vacío significa la raíz del menú (o que el menú ya terminó, ver "
                   "`menu_finalizado`).",
    )
    menu_finalizado = models.BooleanField(
        default=False,
        help_text="True = el bot ya no interpreta los próximos mensajes como una opción elegida "
                   "(se derivó, se terminó, o la organización tiene el menú desactivado/vacío) — "
                   "de ahí en más los mensajes sólo quedan logueados para el operador.",
    )
    estado = models.CharField(max_length=8, choices=Estado.choices, default=Estado.ABIERTA)
    iniciada_at = models.DateTimeField(auto_now_add=True)
    cerrada_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Conversación"
        verbose_name_plural = "Conversaciones"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Conversación #{self.pk} — {self.contact}"


class ConversacionLog(models.Model):
    class Remitente(models.TextChoices):
        CONTACTO = "CONTACTO", "Contacto"
        OPERADOR = "OPERADOR", "Operador"
        SISTEMA = "SISTEMA", "Sistema"

    conversacion = models.ForeignKey(Conversacion, on_delete=models.CASCADE, related_name="mensajes")
    remitente = models.CharField(max_length=8, choices=Remitente.choices)
    texto = models.TextField()
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mensaje de conversación"
        verbose_name_plural = "Mensajes de conversación"
        ordering = ["creado_at"]

    def __str__(self):
        return f"{self.remitente}: {self.texto[:40]}"
