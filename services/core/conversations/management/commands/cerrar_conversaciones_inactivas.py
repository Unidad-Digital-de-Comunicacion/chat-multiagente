"""Cierra automáticamente las conversaciones `ABIERTA` sin actividad
reciente — `BotMessages.minutos_inactividad_cierre`/`mensaje_cierre_
inactividad` (bot_settings/models.py) ya existían como campos de
configuración por organización sin ningún consumidor; este comando es ese
consumidor. `minutos_inactividad_cierre=0` (default) = desactivado, esa
organización no se toca.

Sólo conversaciones "pendiente" de verdad — sin `team` (todavía no se
derivó) Y sin `operador` (nadie la tomó) — pedido explícito: una vez que
se derivó a un equipo o un operador la tomó, se asume que alguien es
responsable de ella y ya no se cierra sola por inactividad, por más
tiempo que pase.

"Actividad" es el último `ConversacionLog` (cualquier remitente — contacto,
operador o sistema), no `Conversacion.updated_at`: ese campo NO se
actualiza en cada mensaje entrante del contacto una vez que el menú ya
terminó (ver `MensajeEntranteView`), así que usarlo daría falsos positivos
de inactividad con conversaciones donde el contacto sigue escribiendo.

Pensado para correr periódicamente desde un loop de supervisord (ver
services/core/docker/supervisord.conf) — no hay cron del sistema operativo
ni Celery/Redis en este proyecto (restricción de stack, CLAUDE.md §1).
Idempotente: sólo toca conversaciones `ABIERTA`, así que correrlo de nuevo
sobre las mismas no hace nada de más."""
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Max, Q
from django.utils import timezone

from bot_settings.models import BotMessages
from conversations.cierre import cerrar_conversacion
from conversations.models import Conversacion

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Cierra las conversaciones abiertas sin actividad reciente, según "
        "BotMessages.minutos_inactividad_cierre de cada organización (0 = desactivado)."
    )

    def handle(self, *args, **options):
        total = 0
        for bot_messages in BotMessages.objects.select_related("organization").filter(minutos_inactividad_cierre__gt=0):
            limite = timezone.now() - timedelta(minutes=bot_messages.minutos_inactividad_cierre)
            # Sin mensajes todavía (no debería pasar — la conversación se
            # crea junto con el primer mensaje — pero cubierto igual) cae a
            # `iniciada_at` en vez de quedar afuera del filtro para siempre.
            candidatas = Conversacion.objects.filter(
                organization=bot_messages.organization, estado=Conversacion.Estado.ABIERTA,
                team__isnull=True, operador__isnull=True,
            ).annotate(ultimo_mensaje_at=Max("mensajes__creado_at")).filter(
                Q(ultimo_mensaje_at__lt=limite) | Q(ultimo_mensaje_at__isnull=True, iniciada_at__lt=limite),
            )
            mensaje = bot_messages.valor_o_default("mensaje_cierre_inactividad")
            for conversacion in candidatas:
                cerrar_conversacion(conversacion, mensaje=mensaje)
                total += 1
                logger.info(
                    "conversación cerrada por inactividad id=%s organization_id=%s minutos_inactividad_cierre=%s",
                    conversacion.id, conversacion.organization_id, bot_messages.minutos_inactividad_cierre,
                )

        if total:
            self.stdout.write(self.style.SUCCESS(f"Cerradas {total} conversación(es) por inactividad."))
