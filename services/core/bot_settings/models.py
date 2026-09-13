from django.db import models

from . import defaults


class BotMessages(models.Model):
    """Mensajes predeterminados del bot para cada sección/acción de la
    conversación (bienvenida, saludos de menú, despedida, derivación, cierre
    por inactividad). Un registro por organización — análogo a
    `ConfiguracionChatbot` del repo `garzamorada/chatbot`, recortado a sólo
    los campos de mensajería (la config de webhook/chatealo se descarta,
    sección 5 de docs/CONTEXTO_PROYECTO.md) y con `organization` en vez de
    ser un singleton global.

    Todo campo de texto puede quedar vacío: en ese caso el bot (Fase 3) usa
    el default de `bot_settings.defaults`, igual que el original."""

    organization = models.OneToOneField(
        "organizations.Organization", on_delete=models.CASCADE, related_name="mensajes_bot",
    )

    menu_activo = models.BooleanField(
        default=True, verbose_name="Usar el menú del bot",
        help_text="Desactivado: no se usa el árbol de menú (ni sus saludos de sección ni la "
                   "derivación por opción elegida) — el contacto sólo recibe el mensaje de "
                   "bienvenida y, sin nada en el medio, la conversación queda directamente en la "
                   "bandeja sin asignar para que cualquier operador la tome. El mensaje de "
                   "despedida y el saludo del operador al tomar la conversación se siguen usando "
                   "en ambos modos. Sólo configuración por ahora: aplicarlo de verdad (saltear el "
                   "bot) es Channel Gateway/Conversation Engine, Fase 3/4 — todavía no implementado.",
    )

    mensaje_bienvenida = models.TextField(
        blank=True, verbose_name="Mensaje de bienvenida (primer contacto)",
        help_text="Se manda una sola vez, la primera vez que el contacto escribe — antes del menú, "
                   "o si el menú está desactivado, antes de que la conversación quede libre para "
                   "que la tome un operador. Se usa en ambos modos. Variable disponible: {nombre}.",
    )
    saludo_inicial = models.TextField(
        blank=True, verbose_name="Saludo del menú principal",
        help_text="Encabezado del menú principal, antes del listado de opciones. Variable: {nombre}.",
    )
    saludo_area = models.TextField(
        blank=True, verbose_name="Saludo de cada menú",
        help_text="Encabezado al entrar a un submenú. Variables: {area} (nombre del submenú) y {nombre}.",
    )
    mensaje_despedida = models.TextField(
        blank=True, verbose_name="Mensaje de despedida",
        help_text='Se usa en ambos modos: lo manda cualquier opción de tipo "Terminar" del árbol '
                   "de menú, o el cierre de la conversación si el menú está desactivado. "
                   "Variable: {nombre}.",
    )
    derivacion_texto = models.CharField(
        max_length=24, blank=True, verbose_name='Texto de la opción "Hablar con un operador"',
        help_text="Cómo aparece la opción en el listado. Máx. 24 caracteres (límite de WhatsApp).",
    )
    derivacion_mensaje = models.TextField(
        blank=True, verbose_name="Mensaje al derivar a un operador",
        help_text="Texto que recibe el contacto al pedir un operador. Variables: {area}, {nombre}.",
    )
    mensaje_cierre_inactividad = models.TextField(
        blank=True, verbose_name="Mensaje de cierre por inactividad",
        help_text="Se manda al cerrar automáticamente una conversación inactiva. Variable: {nombre}.",
    )
    mensaje_operador_toma = models.TextField(
        blank=True, verbose_name="Saludo del operador al tomar la conversación",
        help_text='Se usa siempre, tenga el menú activado o no. Se le sugiere al operador al marcar '
                   'una conversación como "tomada". A diferencia del resto de los campos, acá '
                   "{nombre} es el nombre del OPERADOR, no el del contacto. Es sólo configuración: "
                   "aplicarlo de verdad (sugerirlo/mandarlo al tomar una conversación) es parte del "
                   "Operators Desk, Fase 4/5 — todavía no implementado.",
    )

    minutos_inactividad_cierre = models.PositiveIntegerField(
        default=0, verbose_name="Minutos de inactividad para cerrar la conversación",
        help_text="0 = desactivado (nunca cierra por inactividad).",
    )
    segundos_remostrar_menu = models.PositiveIntegerField(
        default=60, verbose_name="Segundos para volver a mostrar el menú tras una respuesta",
        help_text="Después de una opción tipo Respuesta, esperar estos segundos y volver a mostrar el "
                   "menú donde estaba el contacto. 0 = desactivado.",
    )

    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def para_organizacion(cls, organization):
        obj, _ = cls.objects.get_or_create(organization=organization)
        return obj

    def valor_o_default(self, campo):
        return getattr(self, campo) or defaults.DEFAULT_POR_CAMPO.get(campo, "")

    def __str__(self):
        return f"Mensajes del bot — {self.organization.name}"

    class Meta:
        verbose_name = "Mensajes predeterminados del bot"
        verbose_name_plural = "Mensajes predeterminados del bot"
