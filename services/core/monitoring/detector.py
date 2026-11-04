"""Detección de eventos anómalos. Lo corre `manage.py vigilar_incidentes` en
loop bajo supervisord (mismo patrón que `cerrar_conversaciones_inactivas`:
no hay Celery/Redis en este proyecto).

Reglas (todas agrupan por "huella" para no abrir un incidente por línea):
- Cualquier línea ERROR/CRITICAL de cualquier servicio (incluye los HTTP 5xx,
  que el middleware de acceso loguea como ERROR, y las excepciones).
- Seguridad: una IP bloqueada por intentos de login fallidos, o una ráfaga de
  `MONITOREO_LOGIN_FALLIDOS_UMBRAL` logins fallidos en una misma pasada.
- Caída: un chequeo HTTP de `MONITOREO_CHEQUEOS` (servicios internos y dominios
  públicos detrás del túnel) que falla `MONITOREO_FALLOS_PARA_CAIDA` veces
  seguidas. Se resuelve solo cuando vuelve a responder.
"""
import hashlib
import logging
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from . import logs
from .models import MAX_REQUEST_IDS, ChequeoSalud, CursorLog, Incidente

logger = logging.getLogger("monitoring.detector")

MAX_BYTES_POR_PASADA = 20 * 1024 * 1024
MAX_DETALLE = 8000

# Duplicados de una misma excepción que ya loguea `MiddlewareRequestId` (con
# su request_id): uvicorn la vuelve a loguear sin contexto.
_IGNORAR = [("uvicorn.error", "Exception in ASGI application")]

_RE_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
_RE_HEX = re.compile(r"\b[0-9a-f]{12,}\b", re.I)
_RE_NUM = re.compile(r"\d+")
_RE_IP = re.compile(r"ip=([0-9a-fA-F:.]+)")


def normalizar(mensaje: str) -> str:
    primera = (mensaje or "").splitlines()[0] if mensaje else ""
    primera = _RE_UUID.sub("<uuid>", primera)
    primera = _RE_HEX.sub("<id>", primera)
    return _RE_NUM.sub("#", primera)[:300]


def huella(*partes: str) -> str:
    return hashlib.sha256("|".join(partes).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- lectura


def _leer_desde(ruta, offset: int, tope: int) -> tuple[bytes, int]:
    with open(ruta, "rb") as f:
        f.seek(offset)
        datos = f.read(tope)
    # Sólo líneas completas: una a medio escribir queda para la próxima pasada.
    corte = datos.rfind(b"\n")
    if corte < 0:
        return b"", offset
    return datos[: corte + 1], offset + corte + 1


def leer_lineas_nuevas() -> dict[str, list[dict]]:
    """Líneas escritas desde la pasada anterior, por servicio. La primera vez
    que ve un archivo arranca desde el final (no alerta por historia vieja)."""
    resultado: dict[str, list[dict]] = {}
    for servicio in logs.servicios_con_logs():
        ruta = logs.archivo_actual(servicio)
        try:
            stat = os.stat(ruta)
        except OSError:
            continue
        cursor, creado = CursorLog.objects.get_or_create(
            archivo=str(ruta), defaults={"inode": stat.st_ino, "offset": stat.st_size},
        )
        if creado:
            continue

        crudo = b""
        if cursor.inode != stat.st_ino:
            # Rotó: lo que quedó sin leer del archivo viejo está ahora en `.1`.
            rotado = f"{ruta}.1"
            try:
                if os.stat(rotado).st_ino == cursor.inode:
                    crudo, _ = _leer_desde(rotado, cursor.offset, MAX_BYTES_POR_PASADA)
            except OSError:
                pass
            offset = 0
        else:
            offset = cursor.offset if stat.st_size >= cursor.offset else 0
        nuevo, offset = _leer_desde(ruta, offset, MAX_BYTES_POR_PASADA)
        crudo += nuevo

        cursor.inode, cursor.offset = stat.st_ino, offset
        cursor.save(update_fields=["inode", "offset", "actualizado_at"])
        lineas = [r for r in (logs.parsear_linea(l, servicio) for l in crudo.decode("utf-8", "replace").splitlines()) if r]
        if lineas:
            resultado[servicio] = lineas
    return resultado


# ---------------------------------------------------------------- incidentes


@dataclass
class _Ocurrencia:
    tipo: str
    servicio: str
    titulo: str
    detalle: str = ""
    cantidad: int = 0
    primera: datetime | None = None
    ultima: datetime | None = None
    request_ids: list[str] = field(default_factory=list)

    def sumar(self, ts, request_id="", detalle="", cantidad=1):
        ts = ts or timezone.now()
        self.cantidad += cantidad
        self.primera = min(self.primera, ts) if self.primera else ts
        self.ultima = max(self.ultima, ts) if self.ultima else ts
        if detalle:
            self.detalle = detalle[:MAX_DETALLE]
        if request_id and request_id not in self.request_ids:
            self.request_ids.append(request_id)


def _detalle(registro: dict) -> str:
    return registro["msg"] + (f"\n\n{registro['exc']}" if registro.get("exc") else "")


def analizar(lineas_por_servicio: dict[str, list[dict]]) -> dict[str, _Ocurrencia]:
    """Puro (sin base): de líneas de log a ocurrencias agrupadas por huella."""
    ocurrencias: dict[str, _Ocurrencia] = {}
    fallidos = defaultdict(list)

    for servicio, lineas in lineas_por_servicio.items():
        for r in lineas:
            if r["logger"] == "authentication" and r["msg"].startswith("login fallido"):
                fallidos[servicio].append(r)
                if "bloqueada=True" in r["msg"]:
                    ip = (_RE_IP.search(r["msg"]) or [None, "?"])[1]
                    h = huella("ip-bloqueada", ip)
                    oc = ocurrencias.setdefault(h, _Ocurrencia(
                        "seguridad", servicio, f"IP {ip} bloqueada por intentos de login fallidos",
                    ))
                    oc.sumar(r["ts"], r["request_id"], _detalle(r))
                continue
            if logs.NIVELES.get(r["level"], 20) < logs.NIVELES["ERROR"]:
                continue
            if any(r["logger"] == lg and r["msg"].startswith(m) for lg, m in _IGNORAR):
                continue
            h = huella("error", r["service"], r["logger"], normalizar(r["msg"]))
            primera_linea = (r["msg"].splitlines() or [""])[0][:200]
            oc = ocurrencias.setdefault(h, _Ocurrencia(
                "error", r["service"], f"{r['service']} · {r['logger'] or 'root'}: {primera_linea}",
            ))
            oc.sumar(r["ts"], r["request_id"], _detalle(r))

    umbral = settings.MONITOREO_LOGIN_FALLIDOS_UMBRAL
    for servicio, regs in fallidos.items():
        if len(regs) >= umbral:
            oc = ocurrencias.setdefault(huella("login-rafaga", servicio), _Ocurrencia(
                "seguridad", servicio, "Ráfaga de logins fallidos (posible fuerza bruta)",
            ))
            for r in regs:
                oc.sumar(r["ts"], r["request_id"], _detalle(r))
            oc.detalle = f"{len(regs)} logins fallidos en una sola pasada del detector.\n\nÚltimo: {_detalle(regs[-1])}"
    return ocurrencias


def registrar(h: str, oc: _Ocurrencia) -> Incidente:
    with transaction.atomic():
        incidente = Incidente.objects.select_for_update().filter(huella=h).first()
        if incidente is None:
            return Incidente.objects.create(
                huella=h, tipo=oc.tipo, servicio=oc.servicio, titulo=oc.titulo[:300], detalle=oc.detalle,
                request_ids=oc.request_ids[-MAX_REQUEST_IDS:], ocurrencias=oc.cantidad,
                primera_vez=oc.primera, ultima_vez=oc.ultima,
            )
        if incidente.estado == Incidente.Estado.RESUELTO:
            # Volvió a pasar: se reabre y se vuelve a avisar como nuevo.
            incidente.estado = Incidente.Estado.ABIERTO
            incidente.resuelto_at = incidente.resuelto_por = None
            incidente.notificado_at = None
            incidente.ocurrencias_notificadas = incidente.ocurrencias
        incidente.ocurrencias += oc.cantidad
        incidente.ultima_vez = max(incidente.ultima_vez, oc.ultima)
        incidente.detalle = oc.detalle or incidente.detalle
        ids = [i for i in incidente.request_ids if i not in oc.request_ids] + oc.request_ids
        incidente.request_ids = ids[-MAX_REQUEST_IDS:]
        incidente.save()
        return incidente


def procesar_logs() -> int:
    ocurrencias = analizar(leer_lineas_nuevas())
    for h, oc in ocurrencias.items():
        registrar(h, oc)
    return len(ocurrencias)


# ---------------------------------------------------------------- salud


def chequear_salud() -> list[Incidente]:
    """Devuelve los incidentes de caída que se resolvieron solos en esta pasada
    (para avisar "volvió a responder")."""
    recuperados = []
    ahora = timezone.now()
    for nombre, url in settings.MONITOREO_CHEQUEOS:
        chequeo, _ = ChequeoSalud.objects.get_or_create(nombre=nombre, defaults={"url": url})
        try:
            respuesta = requests.get(url, timeout=settings.MONITOREO_TIMEOUT_SEGUNDOS)
            ok = respuesta.status_code < 500
            detalle = f"HTTP {respuesta.status_code}"
        except requests.RequestException as exc:
            ok, detalle = False, f"{type(exc).__name__}: {exc}"[:500]

        chequeo.url, chequeo.ok, chequeo.ultimo_detalle, chequeo.ultimo_chequeo_at = url, ok, detalle, ahora
        chequeo.fallos_consecutivos = 0 if ok else chequeo.fallos_consecutivos + 1
        chequeo.save()

        h = huella("caida", nombre)
        if ok:
            abierto = Incidente.objects.filter(huella=h, estado=Incidente.Estado.ABIERTO).first()
            if abierto:
                abierto.estado, abierto.resuelto_at = Incidente.Estado.RESUELTO, ahora
                abierto.save(update_fields=["estado", "resuelto_at"])
                logger.info("chequeo %s volvió a responder (%s)", nombre, detalle)
                recuperados.append(abierto)
        elif chequeo.fallos_consecutivos >= settings.MONITOREO_FALLOS_PARA_CAIDA:
            oc = _Ocurrencia("caida", nombre, f"{nombre} no responde ({url})")
            oc.sumar(ahora, detalle=f"{chequeo.fallos_consecutivos} chequeos fallidos seguidos. Último: {detalle}")
            registrar(h, oc)
    return recuperados
