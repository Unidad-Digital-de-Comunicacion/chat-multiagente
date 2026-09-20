"""Handler de excepciones de DRF que envuelve toda respuesta de error en
`{"error": {"code": "...", "detail": "..."}}` (BUENAS-PRACTICAS-API-REST.md
§4) — reemplaza el shape default de DRF (`{"detail": "..."}` o
`{"campo": ["msg"]}` suelto) para que sea consistente en toda la API."""
import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

# Nombre de clase de la excepción -> código estable. Explícito en vez de
# usar `exc.default_code` directo porque DRF lo pone medio inconsistente
# (`ValidationError.default_code == "invalid"`, no "validation_error") y
# porque `exc` puede ser una excepción de Django (`Http404`,
# `django.core.exceptions.PermissionDenied`) sin ese atributo — ver
# `_CODE_POR_STATUS` para esos casos.
_CODE_POR_EXCEPCION = {
    "ValidationError": "validation_error",
    "AuthenticationFailed": "authentication_failed",
    "NotAuthenticated": "not_authenticated",
    "PermissionDenied": "permission_denied",
    "NotFound": "not_found",
    "MethodNotAllowed": "method_not_allowed",
    "NotAcceptable": "not_acceptable",
    "UnsupportedMediaType": "unsupported_media_type",
    "ParseError": "parse_error",
    "Throttled": "throttled",
}

# Respaldo por status code — cubre `Http404`/`PermissionDenied` de Django
# (que DRF traduce internamente antes de armar la Response, pero el `exc`
# que llega acá sigue siendo el original, sin nombre de clase de DRF) y
# cualquier excepción no contemplada arriba.
_CODE_POR_STATUS = {
    400: "validation_error",
    401: "not_authenticated",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    406: "not_acceptable",
    415: "unsupported_media_type",
    429: "throttled",
}


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)

    if response is None:
        # DRF no reconoce esta excepción (bug real, no un error de cliente)
        # — nunca exponer el traceback en la respuesta (BUENAS-PRACTICAS
        # §4), pero sí loguearlo entero del lado del servidor. Devolver acá
        # una Response (nunca None) evita que DRF vuelva a levantar la
        # excepción hacia Django, que sí podría mostrar la página de debug.
        logger.exception("Excepción no manejada en un endpoint de la API", exc_info=exc)
        return Response(
            {"error": {"code": "internal_error", "detail": "Ocurrió un error interno. Volvé a intentar más tarde."}},
            status=500,
        )

    code = _CODE_POR_EXCEPCION.get(type(exc).__name__) or _CODE_POR_STATUS.get(response.status_code) or "error"

    detalle = response.data
    # No es un "ad hoc narrowing" de input externo sin parsear: este
    # handler ES el borde donde entra la forma dinámica que arma DRF (según
    # `exc.detail` sea string, dict o list) — no hay un punto más atrás
    # donde tipar esto. DRF ya envuelve un detalle simple (string) como
    # `{"detail": "..."}` antes de que este handler corra; desenvolverlo así
    # evita `{"error": {"detail": {"detail": "..."}}}` doblemente anidado.
    # Un error de validación real (`{"campo": [...]}`) nunca tiene
    # exactamente esa única clave, así que esto no le pisa nada.
    if isinstance(detalle, dict) and list(detalle.keys()) == ["detail"]:  # noqa: ASP002
        detalle = detalle["detail"]

    response.data = {"error": {"code": code, "detail": detalle}}
    return response
