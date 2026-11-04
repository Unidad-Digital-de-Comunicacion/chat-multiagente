from datetime import timedelta

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import mixins, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsPlatformSuperuser

from . import logs
from .models import ChequeoSalud, Incidente
from .serializers import ChequeoSaludSerializer, IncidenteSerializer, LineaLogSerializer

LIMITE_MAXIMO_LINEAS = 2000


class IncidenteViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet,
):
    """GET/PATCH /api/core/plataforma/incidentes/ — sólo el superusuario de
    plataforma. Filtros: `?estado=abierto|resuelto`, `?tipo=`, `?servicio=`.
    PATCH sólo cambia `estado` (resolver o reabrir a mano)."""

    serializer_class = IncidenteSerializer
    permission_classes = [IsPlatformSuperuser]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        qs = Incidente.objects.select_related("resuelto_por")
        for campo in ("estado", "tipo", "servicio"):
            valor = self.request.query_params.get(campo)
            if valor:
                qs = qs.filter(**{campo: valor})
        return qs

    def perform_update(self, serializer):
        estado = serializer.validated_data.get("estado")
        if estado == Incidente.Estado.RESUELTO:
            serializer.save(resuelto_at=timezone.now(), resuelto_por=self.request.user)
        elif estado == Incidente.Estado.ABIERTO:
            serializer.save(resuelto_at=None, resuelto_por=None)
        else:
            serializer.save()


def _fecha(valor, nombre):
    if not valor:
        return None
    fecha = parse_datetime(valor)
    if fecha is None:
        raise ValidationError({nombre: ["Fecha inválida, se espera ISO 8601."]})
    return fecha if fecha.tzinfo else timezone.make_aware(fecha)


class LogsView(APIView):
    """GET /api/core/plataforma/logs/ — líneas de log de todos los servicios,
    en orden cronológico. Parámetros (todos opcionales): `desde`/`hasta` (ISO
    8601, default: la última hora), `servicio` (uno o varios separados por
    coma), `nivel` (mínimo: INFO/WARNING/ERROR), `request_id`, `q` (texto),
    `limite` (default 500, máx. 2000; si hay más se devuelven las últimas)."""

    permission_classes = [IsPlatformSuperuser]

    def get(self, request):
        p = request.query_params
        hasta = _fecha(p.get("hasta"), "hasta") or timezone.now()
        desde = _fecha(p.get("desde"), "desde") or hasta - timedelta(hours=1)
        if desde > hasta:
            raise ValidationError({"desde": ["Tiene que ser anterior a `hasta`."]})
        try:
            limite = max(1, min(int(p.get("limite", 500)), LIMITE_MAXIMO_LINEAS))
        except ValueError:
            raise ValidationError({"limite": ["Tiene que ser un número."]}) from None
        servicios = [s for s in (p.get("servicio") or "").split(",") if s] or None

        resultado = logs.buscar(
            desde=desde, hasta=hasta, servicios=servicios, nivel_min=p.get("nivel"),
            request_id=p.get("request_id") or None, texto=p.get("q") or None, limite=limite,
        )
        return Response({
            "servicios_disponibles": logs.servicios_con_logs(),
            "desde": desde,
            "hasta": hasta,
            "truncado": resultado.truncado,
            "lineas": LineaLogSerializer(resultado.lineas, many=True).data,
        })


class ChequeosSaludView(APIView):
    """GET /api/core/plataforma/chequeos-salud/ — último resultado de cada
    chequeo HTTP que corre el detector."""

    permission_classes = [IsPlatformSuperuser]

    def get(self, request):
        return Response(ChequeoSaludSerializer(ChequeoSalud.objects.all(), many=True).data)
