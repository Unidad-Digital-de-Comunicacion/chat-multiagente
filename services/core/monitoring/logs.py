"""Lectura de los archivos de log de todos los servicios.

Cada servicio escribe JSON por línea en `<LOGS_TODOS_DIR>/<servicio>/<servicio>.log`
(+ `.log.1` … `.log.N` rotados) — ver `common/observabilidad.py` y
`app/observabilidad.py` de cada servicio FastAPI. Core monta la carpeta entera
`./logs` del host en sólo lectura para poder leer todos.

Sin base de datos de logs a propósito (CLAUDE.md: nada de Elasticsearch/Loki
ni tecnologías nuevas): los archivos son la fuente, y con rotación acotada
(10 MB × 10 por servicio por default) recorrerlos alcanza para esta etapa.
"""
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings

NIVELES = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}


def directorio_logs() -> Path | None:
    raiz = settings.LOGS_TODOS_DIR
    return Path(raiz) if raiz and os.path.isdir(raiz) else None


def servicios_con_logs() -> list[str]:
    raiz = directorio_logs()
    if not raiz:
        return []
    return sorted(p.name for p in raiz.iterdir() if p.is_dir() and (p / f"{p.name}.log").exists())


def archivo_actual(servicio: str) -> Path | None:
    raiz = directorio_logs()
    return raiz / servicio / f"{servicio}.log" if raiz else None


def _archivos_de(servicio: str) -> list[Path]:
    raiz = directorio_logs()
    if not raiz:
        return []
    carpeta = raiz / servicio
    return [p for p in carpeta.glob(f"{servicio}.log*") if not p.name.endswith(".lock") and p.is_file()]


def _parsear_ts(valor) -> datetime | None:
    if not valor:
        return None
    try:
        ts = datetime.fromisoformat(valor)
    except (TypeError, ValueError):
        return None
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def parsear_linea(linea: str, servicio: str) -> dict | None:
    linea = linea.strip()
    if not linea:
        return None
    try:
        datos = json.loads(linea)
        if not isinstance(datos, dict):
            raise ValueError
    except ValueError:
        # Algo que no pasó por el formatter JSON (no debería, pero no se pierde).
        datos = {"level": "INFO", "msg": linea}
    return {
        "ts": _parsear_ts(datos.get("ts")),
        "level": str(datos.get("level") or "INFO").upper(),
        "service": datos.get("service") or servicio,
        "logger": datos.get("logger") or "",
        "msg": str(datos.get("msg") or ""),
        "request_id": datos.get("request_id") or "",
        "exc": datos.get("exc") or "",
    }


@dataclass
class ResultadoBusqueda:
    lineas: list[dict]
    truncado: bool


def buscar(
    *, desde: datetime, hasta: datetime, servicios: list[str] | None = None, nivel_min: str | None = None,
    request_id: str | None = None, texto: str | None = None, limite: int = 500,
) -> ResultadoBusqueda:
    """Líneas de todos los servicios pedidos dentro de [desde, hasta], en orden
    cronológico. Si hay más de `limite`, devuelve las ÚLTIMAS `limite` (lo más
    cercano a "ahora" o al final del incidente) y marca `truncado`."""
    nivel_valor = NIVELES.get((nivel_min or "").upper(), 0)
    texto_lower = (texto or "").lower()
    elegidos = servicios or servicios_con_logs()
    encontradas = []
    for servicio in elegidos:
        for archivo in _archivos_de(servicio):
            try:
                if datetime.fromtimestamp(archivo.stat().st_mtime, tz=timezone.utc) < desde:
                    continue  # el archivo se terminó de escribir antes de la ventana
                with archivo.open("r", encoding="utf-8", errors="replace") as f:
                    for cruda in f:
                        # Filtros baratos antes de parsear JSON.
                        if request_id and request_id not in cruda:
                            continue
                        if texto_lower and texto_lower not in cruda.lower():
                            continue
                        registro = parsear_linea(cruda, servicio)
                        if not registro or not registro["ts"]:
                            continue
                        if not (desde <= registro["ts"] <= hasta):
                            continue
                        if NIVELES.get(registro["level"], 20) < nivel_valor:
                            continue
                        if request_id and registro["request_id"] != request_id:
                            continue
                        encontradas.append(registro)
            except OSError:
                continue
    encontradas.sort(key=lambda r: r["ts"])
    truncado = len(encontradas) > limite
    return ResultadoBusqueda(lineas=encontradas[-limite:] if truncado else encontradas, truncado=truncado)
