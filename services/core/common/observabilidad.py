"""Logging estructurado + correlación de requests en Core.

Mismo formato de línea que `app/observabilidad.py` de los servicios FastAPI
(JSON por línea: `ts`, `level`, `service`, `logger`, `msg`, `request_id`,
`exc`) — así `monitoring.logs` lee los archivos de todos los servicios con un
solo parser. El handler de archivo se configura en `settings.LOGGING`.
"""
import contextvars
import json
import logging
import time
import uuid
from datetime import datetime, timezone

request_id_actual: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

_RUTAS_SIN_LOG_DE_ACCESO = ("/health",)


class FormatoJson(logging.Formatter):
    def __init__(self, servicio="core"):
        super().__init__()
        self.servicio = servicio

    def format(self, record):
        datos = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "service": self.servicio,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": (
                getattr(record, "request_id", "")
                or request_id_actual.get()
                # `django.request` loguea los 4xx/5xx DESPUÉS de que el
                # middleware ya limpió el contextvar, pero pasa el request.
                or getattr(getattr(record, "request", None), "request_id", "")
            ),
        }
        if record.exc_info:
            datos["exc"] = self.formatException(record.exc_info)
        return json.dumps(datos, ensure_ascii=False)


def headers_request_id():
    """Para sumar a las llamadas salientes hacia otros servicios nuestros
    (`requests.post(..., headers={..., **headers_request_id()})`)."""
    rid = request_id_actual.get()
    return {"X-Request-ID": rid} if rid else {}


class RequestIdMiddleware:
    """Toma `X-Request-ID` (otro servicio nuestro) o `Cf-Ray` (Cloudflare) o
    genera uno; lo deja en el contextvar para que salga en cada línea de log
    del request, lo devuelve en la respuesta y loguea una línea de acceso.
    Un 5xx va como WARNING y no ERROR: Django ya lo loguea como ERROR por su
    cuenta (`django.request`, con el traceback) y eso es lo que abre el
    incidente — dos ERROR por la misma falla abrirían dos incidentes."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger("acceso")

    def __call__(self, request):
        rid = (request.headers.get("X-Request-ID") or request.headers.get("Cf-Ray") or uuid.uuid4().hex[:16])[:64]
        request.request_id = rid
        token = request_id_actual.set(rid)
        inicio = time.monotonic()
        try:
            response = self.get_response(request)
            response["X-Request-ID"] = rid
            if not request.path.startswith(_RUTAS_SIN_LOG_DE_ACCESO):
                ms = int((time.monotonic() - inicio) * 1000)
                nivel = logging.WARNING if response.status_code >= 500 else logging.INFO
                self.logger.log(nivel, "HTTP %s %s %s %sms", response.status_code, request.method, request.path, ms)
            return response
        finally:
            request_id_actual.reset(token)
