"""Aviso por mail de incidentes nuevos/reabiertos/que siguen creciendo.

Un solo mail por pasada del detector con todo lo pendiente (no uno por
incidente), y un incidente que sigue abierto sólo se vuelve a avisar si sumó
ocurrencias Y pasaron `ALERTAS_RENOTIFICAR_MINUTOS` desde el último aviso —
para que un error que se repite cada segundo no llene la casilla.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import F, Q
from django.utils import timezone

from .models import Incidente

logger = logging.getLogger("monitoring.alertas")


def pendientes_de_aviso():
    limite = timezone.now() - timedelta(minutes=settings.ALERTAS_RENOTIFICAR_MINUTOS)
    return Incidente.objects.filter(estado=Incidente.Estado.ABIERTO).filter(
        Q(notificado_at__isnull=True)
        | Q(notificado_at__lte=limite, ocurrencias__gt=F("ocurrencias_notificadas")),
    ).order_by("primera_vez")


def _link(incidente) -> str:
    base = (settings.ALERTAS_PANEL_URL or "").rstrip("/")
    return f"{base}/plataforma/incidentes?id={incidente.pk}" if base else f"(incidente #{incidente.pk})"


def _hora(dt) -> str:
    return timezone.localtime(dt).strftime("%d/%m/%Y %H:%M:%S")


def armar_mensaje(incidentes, recuperados) -> tuple[str, str]:
    partes = []
    if incidentes:
        partes.append(f"{len(incidentes)} incidente(s) que requieren atención:\n")
        for i in incidentes:
            nuevo = i.notificado_at is None
            partes.append(
                f"{'NUEVO' if nuevo else 'SIGUE'} · [{i.get_tipo_display()}] {i.titulo}\n"
                f"  Servicio: {i.servicio} · Ocurrencias: {i.ocurrencias}"
                f"{'' if nuevo else f' (+{i.ocurrencias - i.ocurrencias_notificadas} desde el último aviso)'}\n"
                f"  Primera vez: {_hora(i.primera_vez)} · Última: {_hora(i.ultima_vez)} (hora de Argentina)\n"
                f"  Request IDs: {', '.join(i.request_ids[-5:]) or '—'}\n"
                f"  Ver en el panel: {_link(i)}\n"
                f"  Detalle:\n    " + "\n    ".join(i.detalle[:1500].splitlines()) + "\n",
            )
    if recuperados:
        partes.append("Recuperados (volvieron a responder solos):\n")
        partes.extend(f"  · {i.titulo} — {_link(i)}\n" for i in recuperados)

    if incidentes:
        nuevos = sum(1 for i in incidentes if i.notificado_at is None)
        asunto = f"[UDC Chat] {len(incidentes)} incidente(s)" + (f", {nuevos} nuevo(s)" if nuevos else "")
        asunto += f": {incidentes[0].titulo}"[:120]
    else:
        asunto = f"[UDC Chat] Recuperado: {recuperados[0].titulo}"[:150]
    return asunto[:200], "\n".join(partes)


def notificar(recuperados=()) -> int:
    destinatarios = settings.ALERTAS_EMAIL_DESTINO
    incidentes = list(pendientes_de_aviso())
    recuperados = list(recuperados)
    if not destinatarios or not (incidentes or recuperados):
        return 0
    asunto, cuerpo = armar_mensaje(incidentes, recuperados)
    try:
        send_mail(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, destinatarios, fail_silently=False)
    except Exception:
        # Queda como incidente propio (ERROR en core.log) y se reintenta en
        # la próxima pasada, porque los pendientes no se marcan como avisados.
        logger.exception("no se pudo mandar el mail de alertas a %s", ", ".join(destinatarios))
        return 0
    ahora = timezone.now()
    for i in incidentes:
        Incidente.objects.filter(pk=i.pk).update(notificado_at=ahora, ocurrencias_notificadas=i.ocurrencias)
    logger.info("alerta enviada a %s: %s incidente(s), %s recuperado(s)", ", ".join(destinatarios),
                len(incidentes), len(recuperados))
    return len(incidentes)
