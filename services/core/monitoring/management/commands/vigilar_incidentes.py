"""Una pasada del detector: logs nuevos -> incidentes, chequeos de salud,
mail. El loop lo hace supervisord (`docker/supervisord.conf`, programa
`vigilar_incidentes`), igual que `cerrar_conversaciones_inactivas`."""
import logging

from django.core.management.base import BaseCommand

from monitoring import alertas, detector

logger = logging.getLogger("monitoring.vigilar")


class Command(BaseCommand):
    help = "Revisa los logs nuevos de todos los servicios y la salud de los endpoints; avisa por mail."

    def handle(self, *args, **options):
        # Cada etapa por separado: que falle una (ej. el SMTP) no frena las otras.
        recuperados = []
        try:
            detector.procesar_logs()
        except Exception:
            logger.exception("falló el análisis de logs")
        try:
            recuperados = detector.chequear_salud()
        except Exception:
            logger.exception("fallaron los chequeos de salud")
        try:
            alertas.notificar(recuperados)
        except Exception:
            logger.exception("falló el envío de alertas")
