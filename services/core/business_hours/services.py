"""Lógica de horario hábil. Adaptada de `chatbot/horarios.py` del repo
github.com/garzamorada/chatbot: misma lógica de fechas, con todas las
consultas ahora filtradas por organización (sección 5 de
docs/CONTEXTO_PROYECTO.md)."""
import datetime as dt
import logging

from django.utils import timezone

from . import feriados_client
from .models import DiaExcepcional, HorarioAtencion

logger = logging.getLogger("business_hours")

HORIZONTE_DIAS = 60
GRANULARIDAD_MIN = 30
HORA_GRILLA_INICIO = dt.time(7, 0)
HORA_GRILLA_FIN = dt.time(22, 0)


def generar_slots_grilla():
    """Horas (`datetime.time`, como 'HH:MM') de la grilla visual del panel de
    administración, cada GRANULARIDAD_MIN minutos."""
    slots = []
    actual = dt.datetime.combine(dt.date.min, HORA_GRILLA_INICIO)
    fin = dt.datetime.combine(dt.date.min, HORA_GRILLA_FIN)
    while actual < fin:
        slots.append(actual.time())
        actual += dt.timedelta(minutes=GRANULARIDAD_MIN)
    return slots


def expandir_rango_a_horas(hora_inicio, hora_fin):
    """Horas de inicio de cada slot de GRANULARIDAD_MIN cubiertas por
    [hora_inicio, hora_fin) — para pre-pintar la grilla a partir de un rango
    ya guardado."""
    horas = []
    actual = dt.datetime.combine(dt.date.min, hora_inicio)
    fin = dt.datetime.combine(dt.date.min, hora_fin)
    while actual < fin:
        horas.append(actual.time())
        actual += dt.timedelta(minutes=GRANULARIDAD_MIN)
    return horas


def merge_horas_a_rangos(horas):
    """A partir de horas de inicio de slot pintadas en la grilla, arma rangos
    [(inicio, fin), ...] contiguos — para convertir la selección del panel en
    filas de HorarioAtencion."""
    horas = sorted(set(horas))
    if not horas:
        return []
    rangos = []
    inicio = horas[0]
    anterior = horas[0]
    paso = dt.timedelta(minutes=GRANULARIDAD_MIN)
    for h in horas[1:]:
        esperado = (dt.datetime.combine(dt.date.min, anterior) + paso).time()
        if h == esperado:
            anterior = h
        else:
            fin = (dt.datetime.combine(dt.date.min, anterior) + paso).time()
            rangos.append((inicio, fin))
            inicio = h
            anterior = h
    fin = (dt.datetime.combine(dt.date.min, anterior) + paso).time()
    rangos.append((inicio, fin))
    return rangos


def _rangos_del_dia(organization_id, fecha):
    """(hora_inicio, hora_fin) vigentes para esa fecha y organización. Una
    excepción propia de la organización pisa al catálogo compartido de
    feriados nacionales (organization=None) para la misma fecha."""
    excepcion = DiaExcepcional.objects.filter(organization_id=organization_id, fecha=fecha).first()
    if excepcion is None:
        excepcion = DiaExcepcional.objects.filter(organization__isnull=True, fecha=fecha).first()

    if excepcion:
        if excepcion.tipo == DiaExcepcional.Tipo.HORARIO_REDUCIDO and excepcion.hora_inicio and excepcion.hora_fin:
            return [(excepcion.hora_inicio, excepcion.hora_fin)]
        return []  # FERIADO o ASUETO: cerrado todo el día

    qs = HorarioAtencion.objects.filter(
        organization_id=organization_id, dia_semana=fecha.weekday(), activo=True,
    ).order_by("hora_inicio")
    return [(h.hora_inicio, h.hora_fin) for h in qs]


def esta_en_horario(organization_id, momento=None):
    """Si la organización todavía no configuró ningún horario semanal, no se
    restringe nada (la derivación a un operador siempre está disponible)."""
    if not HorarioAtencion.objects.filter(organization_id=organization_id).exists():
        return True
    momento = momento or timezone.localtime()
    for inicio, fin in _rangos_del_dia(organization_id, momento.date()):
        if inicio <= momento.time() <= fin:
            return True
    return False


def proxima_apertura(organization_id, momento=None):
    """Próximo datetime (aware) en que arranca una franja de atención de esta
    organización, buscando hacia adelante. None si no hay ninguna dentro del
    horizonte de búsqueda."""
    momento = momento or timezone.localtime()
    tz = timezone.get_current_timezone()

    for offset in range(HORIZONTE_DIAS):
        fecha = momento.date() + dt.timedelta(days=offset)
        for inicio, fin in _rangos_del_dia(organization_id, fecha):
            inicio_dt = timezone.make_aware(dt.datetime.combine(fecha, inicio), tz)
            fin_dt = timezone.make_aware(dt.datetime.combine(fecha, fin), tz)
            if offset == 0 and momento > fin_dt:
                continue  # esa franja de hoy ya pasó
            if offset == 0 and inicio_dt <= momento <= fin_dt:
                return momento  # ya está dentro de horario ahora mismo
            return inicio_dt
    return None


_DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def mensaje_fuera_de_horario(organization_id, momento=None):
    momento = momento or timezone.localtime()
    proxima = proxima_apertura(organization_id, momento)
    if proxima is None or proxima <= momento:
        return ""
    dia_txt = _DIAS_ES[proxima.weekday()]
    return (
        "En este momento estamos fuera de nuestro horario de atención para hablar con un operador. "
        f"El próximo horario disponible es el {dia_txt} {proxima:%d/%m} a las {proxima:%H:%M}hs."
    )


def sincronizar_feriados(anio):
    """Trae los feriados/no laborables nacionales de ese año y los carga como
    DiaExcepcional compartido (organization=None). No pisa filas que una
    organización haya cargado a mano para su propia fecha — sólo crea las que
    faltan del catálogo compartido y actualiza las que generó ella misma."""
    try:
        feriados = feriados_client.obtener_feriados(anio)
    except Exception:
        logger.exception("No se pudo sincronizar feriados del año %s", anio)
        return False

    for f in feriados:
        try:
            fecha = dt.date.fromisoformat(f["fecha"])
        except (KeyError, ValueError, TypeError):
            continue
        nombre = f.get("nombre") or "Feriado nacional"

        obj, created = DiaExcepcional.objects.get_or_create(
            organization=None, fecha=fecha,
            defaults={"tipo": DiaExcepcional.Tipo.FERIADO, "descripcion": nombre, "sincronizado": True},
        )
        if not created and obj.sincronizado and (obj.tipo != DiaExcepcional.Tipo.FERIADO or obj.descripcion != nombre):
            obj.tipo = DiaExcepcional.Tipo.FERIADO
            obj.descripcion = nombre
            obj.save(update_fields=["tipo", "descripcion"])
    return True
