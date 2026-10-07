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
sirve para filtrar la bandeja por equipo.

`ConversacionEtiqueta`/`ConversacionObservacion`/`ConversacionNotaInterna`
(más abajo) son lo que la sección 11/Fase 5 documentaba como "etiquetas
sobre una conversación" y "observaciones de resolución" del futuro
Operators Desk Service — implementadas acá directamente por el mismo
motivo que el resto de esta app (MVP contra Core, sin BFF aparte, ver
`users.group_permissions`). `ConversacionNotaInterna` es un recorte
deliberado del "chat interno entre operadores" que documentaba la Fase 4
(Conversation Engine): ahí se pensó como mensajería 1:1 arbitraria entre
operadores con WebSocket, sin pasar por ninguna conversación — acá es un
hilo de notas internas ACOTADO a una conversación puntual (lo que un
operador necesita para dejarle contexto a otro sobre ESE chat), sin
WebSocket (Core no tiene infraestructura de tiempo real); un cliente que
necesite notificación instantánea debe hacer polling, igual que con
`mensajes`/`etiquetas`/`observaciones`."""
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
                   "reclamarla hasta que venza. Se pone en +2 minutos al tomarla "
                   "(`ConversacionViewSet.tomar`) y se renueva en cada `responder`; una vez "
                   "vencida, cualquier operador la puede reclamar.",
    )
    team = models.ForeignKey(
        "teams.Team", on_delete=models.SET_NULL, null=True, blank=True, related_name="conversaciones",
        help_text="Se completa al elegir una opción de menú tipo Derivación o al derivar a mano "
                   "— queda en la bandeja general de ese equipo (sin `operador`) hasta que "
                   "alguien la toma; no dispara una asignación automática a un operador puntual "
                   "(`conversations.asignacion.asignar_round_robin` existe como utilidad "
                   "independiente, pero ningún call site la usa todavía — roadmap, ver docs/"
                   "CONTEXTO_PROYECTO.md).",
    )
    derivada_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Cuándo se completó `team` por última vez — tanto la derivación automática del "
                   "árbol de menú (`menu_engine.procesar_seleccion`) como la manual "
                   "(`ConversacionViewSet.derivar`) la actualizan. Sólo para el historial "
                   "(`ver_historial_conversacion`) — no es una bitácora de TODAS las derivaciones, "
                   "sólo la más reciente.",
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
        permissions = [
            (
                "ver_historial_conversacion",
                "Puede ver el historial resumido de conversaciones (inicio/derivación/fin, "
                "sin mensajes/etiquetas/notas)",
            ),
            (
                "tomar_sin_derivar",
                "Puede tomar una conversación todavía sin derivar a un equipo (sin este permiso, "
                "sólo se pueden tomar las ya derivadas)",
            ),
        ]

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


class ConversacionEtiqueta(models.Model):
    """Qué etiquetas del catálogo (`tags.Etiqueta` — generales, de equipo, o
    una de las 7 de sistema) tiene aplicadas una conversación puntual, quién
    la aplicó y cuándo. Las de sistema son mutuamente excluyentes entre sí
    (sólo puede haber una activa a la vez — pendiente/asignada/tomada/
    en_proceso/en_pausa/rechazado/resuelto, ver `views.py::
    ConversacionViewSet.etiquetas`); las de equipo también son mutuamente
    excluyentes entre sí, en un eje independiente (sólo puede haber una a
    la vez, sincronizada sola — ver `etiqueta_sistema.
    sincronizar_etiqueta_equipo`); sólo las generales/personalizadas son
    libremente acumulables."""

    conversacion = models.ForeignKey(Conversacion, on_delete=models.CASCADE, related_name="etiquetas_aplicadas")
    etiqueta = models.ForeignKey("tags.Etiqueta", on_delete=models.CASCADE, related_name="+")
    aplicada_por = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    aplicada_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Etiqueta de conversación"
        verbose_name_plural = "Etiquetas de conversación"
        ordering = ["etiqueta__orden", "etiqueta__nombre"]
        constraints = [
            models.UniqueConstraint(fields=["conversacion", "etiqueta"], name="unique_etiqueta_por_conversacion"),
        ]

    def __str__(self):
        return f"{self.conversacion_id} — {self.etiqueta.nombre}"


class ConversacionObservacion(models.Model):
    """Nota de texto libre que un operador deja sobre una conversación, para
    dar contexto a otros operadores. `views.py::ConversacionViewSet.
    etiquetas` exige una de estas (no vacía) al aplicar cualquiera de las 3
    etiquetas de sistema "resuelto"/"rechazado"/"en_pausa" — el resto del
    tiempo es opcional, se puede cargar en cualquier momento vía
    `observaciones`."""

    conversacion = models.ForeignKey(Conversacion, on_delete=models.CASCADE, related_name="observaciones")
    operador = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    texto = models.TextField()
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Observación de conversación"
        verbose_name_plural = "Observaciones de conversación"
        ordering = ["creado_at"]

    def __str__(self):
        return f"{self.conversacion_id}: {self.texto[:40]}"


class EnvioSaliente(models.Model):
    """Auditoría + cola de reintento para un mensaje saliente puntual hacia
    el contacto (`channel_gateway_client.enviar_con_reintentos`) — Core NO
    tiene un broker de colas de verdad (Kafka/RabbitMQ/Redis quedan afuera
    por la sección 1 de docs/CONTEXTO_PROYECTO.md, "stack cerrado"), así
    que esto es sólo una tabla de Postgres: registra cada intento real de
    entrega. Los reintentos (hasta 3, con backoff corto) pasan sincrónicos
    dentro del mismo request de `responder`/`cerrar` — no hay ningún
    worker en segundo plano que vuelva a levantar un `PENDIENTE` más
    tarde, así que un `PENDIENTE` que quedó así porque el proceso se cayó
    a mitad de los reintentos (caso raro) se queda así; no se reprocesa
    solo."""

    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ENVIADO = "ENVIADO", "Enviado"
        FALLIDO = "FALLIDO", "Fallido"

    conversacion = models.ForeignKey(Conversacion, on_delete=models.CASCADE, related_name="envios_salientes")
    texto = models.TextField()
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    intentos = models.PositiveSmallIntegerField(default=0)
    ultimo_error = models.CharField(max_length=255, blank=True)
    creado_at = models.DateTimeField(auto_now_add=True)
    actualizado_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Envío saliente"
        verbose_name_plural = "Envíos salientes"
        ordering = ["-creado_at"]

    def __str__(self):
        return f"Conversación #{self.conversacion_id} — {self.estado} ({self.intentos} intentos)"


class ConversacionNotaInterna(models.Model):
    """Hilo de mensajería ENTRE OPERADORES sobre una conversación puntual —
    nunca sale hacia Channel Gateway ni el contacto la ve, a diferencia de
    `ConversacionLog`. Ver el docstring del módulo para el recorte de
    alcance respecto del "chat interno" más genérico que documentaba la
    Fase 4."""

    conversacion = models.ForeignKey(Conversacion, on_delete=models.CASCADE, related_name="notas_internas")
    operador = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    texto = models.TextField()
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Nota interna de conversación"
        verbose_name_plural = "Notas internas de conversación"
        ordering = ["creado_at"]

    def __str__(self):
        return f"{self.conversacion_id}: {self.texto[:40]}"
