"""Logging estructurado + correlación de requests para los servicios FastAPI.

ARCHIVO IDÉNTICO en channel-gateway, conversation-engine, analytics y webchat
(`app/observabilidad.py`) — cada servicio es un contexto de build de Docker
aparte, así que no hay forma de importar un módulo común sin cambiar cómo se
construyen las imágenes. Si se cambia, cambiarlo en los 4 (y en la versión de
Core, `services/core/common/observabilidad.py`, que comparte el formato).

Qué hace:
- Cada línea de log sale como JSON (`ts`, `level`, `service`, `logger`, `msg`,
  `request_id`, `exc`) a stdout (sigue viéndose en `docker compose logs`) y,
  si existe `LOG_DIR`, a `<LOG_DIR>/<servicio>.log` con rotación por tamaño.
  `ConcurrentRotatingFileHandler` y no el `RotatingFileHandler` de la stdlib:
  con varios workers de gunicorn escribiendo al mismo archivo, el de la stdlib
  rota por su cuenta en cada proceso y pierde/pisa líneas. El lock vive en
  `/tmp` (dentro del contenedor), no en el bind mount del host — en Docker
  Desktop sobre Windows el bind mount no soporta bien `flock` — y el archivo
  se cierra entre escrituras (`keep_file_open=False`, ver más abajo).
- `MiddlewareRequestId`: toma `X-Request-ID` (otro servicio nuestro) o
  `Cf-Ray` (Cloudflare) o genera uno, lo deja en un contextvar para que
  aparezca en cada línea de log de ese request, lo devuelve en la respuesta y
  loguea una línea de acceso (ERROR si el status es 5xx — eso es lo que mira
  el detector de incidentes de Core).
- `propagar_request_id`: event hook de httpx que agrega `X-Request-ID` a las
  llamadas salientes, para seguir un mismo pedido entre servicios.
"""
import contextvars
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone

request_id_actual: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

_RUTAS_SIN_LOG_DE_ACCESO = {"/health"}


class FormatoJson(logging.Formatter):
    def __init__(self, servicio: str):
        super().__init__()
        self.servicio = servicio

    def format(self, record: logging.LogRecord) -> str:
        datos = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "service": self.servicio,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", "") or request_id_actual.get(),
        }
        if record.exc_info:
            datos["exc"] = self.formatException(record.exc_info)
        return json.dumps(datos, ensure_ascii=False)


def configurar_logging(servicio: str) -> None:
    """Idempotente: gunicorn importa la app una vez por worker y `--reload`
    la reimporta; sin el chequeo se duplicarían los handlers."""
    raiz = logging.getLogger()
    if getattr(raiz, "_observabilidad_configurada", False):
        return
    formato = FormatoJson(servicio)
    for handler in list(raiz.handlers):
        raiz.removeHandler(handler)

    consola = logging.StreamHandler(sys.stdout)
    consola.setFormatter(formato)
    raiz.addHandler(consola)

    log_dir = os.environ.get("LOG_DIR", "")
    if log_dir and "pytest" not in sys.modules:
        try:
            from concurrent_log_handler import ConcurrentRotatingFileHandler

            os.makedirs(log_dir, exist_ok=True)
            archivo = ConcurrentRotatingFileHandler(
                os.path.join(log_dir, f"{servicio}.log"),
                maxBytes=int(os.environ.get("LOG_MAX_BYTES", str(10 * 1024 * 1024))),
                backupCount=int(os.environ.get("LOG_BACKUPS", "10")),
                encoding="utf-8",
                lock_file_directory="/tmp",
                # Cerrar el archivo después de cada escritura: en Docker Desktop
                # sobre Windows el bind mount no deja renombrar un archivo que
                # otro worker tiene abierto, y la rotación quedaba a medias
                # (archivos `.rotate.<random>` acumulándose sin límite).
                keep_file_open=False,
            )
            archivo.setFormatter(formato)
            raiz.addHandler(archivo)
        except Exception:  # noqa: BLE001 — sin archivo de log se sigue logueando a stdout
            logging.getLogger(__name__).exception("no se pudo abrir el archivo de log en %s", log_dir)

    raiz.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    # Los loggers de gunicorn/uvicorn traen sus propios handlers de texto
    # plano; se los saca para que todo pase por el formato JSON de arriba.
    # El access log de uvicorn se apaga: lo reemplaza `MiddlewareRequestId`.
    for nombre in ("gunicorn.error", "uvicorn", "uvicorn.error"):
        logging.getLogger(nombre).handlers.clear()
        logging.getLogger(nombre).propagate = True
    logging.getLogger("uvicorn.access").disabled = True
    logging.getLogger("gunicorn.access").disabled = True
    logging.getLogger("httpx").setLevel(logging.WARNING)
    raiz._observabilidad_configurada = True  # type: ignore[attr-defined]


def _header(scope, nombre: bytes) -> str:
    for clave, valor in scope.get("headers") or []:
        if clave.lower() == nombre:
            return valor.decode("latin-1")
    return ""


class MiddlewareRequestId:
    """Middleware ASGI puro (no `BaseHTTPMiddleware`, que rompe WebSockets y
    streaming). En WebSockets sólo fija el request_id, sin línea de acceso."""

    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger("acceso")

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        rid = (_header(scope, b"x-request-id") or _header(scope, b"cf-ray") or uuid.uuid4().hex[:16])[:64]
        token = request_id_actual.set(rid)
        if scope["type"] == "websocket":
            try:
                await self.app(scope, receive, send)
            finally:
                request_id_actual.reset(token)
            return

        inicio = time.monotonic()
        estado = {"status": 500, "excepcion": False}

        async def send_con_header(mensaje):
            if mensaje["type"] == "http.response.start":
                estado["status"] = mensaje["status"]
                mensaje.setdefault("headers", [])
                mensaje["headers"] = list(mensaje["headers"]) + [(b"x-request-id", rid.encode("latin-1"))]
            await send(mensaje)

        try:
            await self.app(scope, receive, send_con_header)
        except Exception:
            # Una sola línea ERROR (con traceback) por falla: es la que abre el
            # incidente en Core; la de acceso de abajo se omite en este caso.
            estado["excepcion"] = True
            self.logger.exception("HTTP 500 %s %s excepción no manejada", scope.get("method"), scope.get("path"))
            raise
        finally:
            ruta = scope.get("path", "")
            if ruta not in _RUTAS_SIN_LOG_DE_ACCESO and not estado["excepcion"]:
                ms = int((time.monotonic() - inicio) * 1000)
                nivel = logging.ERROR if estado["status"] >= 500 else logging.INFO
                self.logger.log(nivel, "HTTP %s %s %s %sms", estado["status"], scope.get("method"), ruta, ms)
            request_id_actual.reset(token)


async def propagar_request_id(request) -> None:
    """Event hook `request` de httpx."""
    rid = request_id_actual.get()
    if rid and "x-request-id" not in request.headers:
        request.headers["X-Request-ID"] = rid
