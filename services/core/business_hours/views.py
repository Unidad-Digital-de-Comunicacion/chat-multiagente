import datetime as dt

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.permissions import StrictDjangoModelPermissions, require_organization, require_perm
from common.viewsets import OrganizationScopedModelViewSet
from teams.models import Team

from . import services
from .models import DiaExcepcional, HorarioAtencion
from .serializers import (
    DiaExcepcionalSerializer, HorarioAtencionSerializer, HorarioHabilSerializer,
)


def _slots_str():
    return [s.strftime("%H:%M") for s in services.generar_slots_grilla()]


class HorarioAtencionViewSet(OrganizationScopedModelViewSet):
    """Ver también la acción `grilla`: es la forma pensada para que el panel
    de administración cargue el horario semanal (pintar una grilla de medias
    horas), en vez de dar de alta cada franja a mano por separado — mismo
    patrón que la grilla semanal portada de `chatbot/templates/chatbot/lista_horarios.html`."""

    queryset = HorarioAtencion.objects.all()
    serializer_class = HorarioAtencionSerializer
    permission_classes = [IsAuthenticated, StrictDjangoModelPermissions]

    @action(detail=False, methods=["get", "post"])
    def grilla(self, request):
        organization_id = require_organization(request)
        slots = _slots_str()

        if request.method == "GET":
            celdas = []
            for h in HorarioAtencion.objects.filter(organization_id=organization_id, activo=True):
                for hora in services.expandir_rango_a_horas(h.hora_inicio, h.hora_fin):
                    celdas.append(f"{h.dia_semana}-{hora.strftime('%H:%M')}")
            return Response({"slots": slots, "celdas": celdas})

        require_perm(request, "business_hours.change_horarioatencion")

        celdas = request.data.get("celdas")
        if not isinstance(celdas, list):
            raise ValidationError({"celdas": "Se espera una lista de claves 'dia-HH:MM'."})

        por_dia = {}
        for celda in celdas:
            try:
                dia_str, hora_str = celda.split("-", 1)
                dia = int(dia_str)
                hora = dt.datetime.strptime(hora_str, "%H:%M").time()
            except (ValueError, AttributeError):
                raise ValidationError({"celdas": f"Clave inválida: {celda!r}"})
            if not 0 <= dia <= 6:
                raise ValidationError({"celdas": f"Día inválido: {dia}"})
            por_dia.setdefault(dia, []).append(hora)

        with transaction.atomic():
            HorarioAtencion.objects.filter(organization_id=organization_id).delete()
            nuevas = [
                HorarioAtencion(organization_id=organization_id, dia_semana=dia, hora_inicio=inicio, hora_fin=fin)
                for dia, horas in por_dia.items()
                for inicio, fin in services.merge_horas_a_rangos(horas)
            ]
            HorarioAtencion.objects.bulk_create(nuevas)

        return Response({"slots": slots, "celdas": celdas})


class DiaExcepcionalViewSet(OrganizationScopedModelViewSet):
    """Además de sus propias excepciones, cada organización ve (sin poder
    editar) el catálogo compartido de feriados nacionales
    (`organization=None`, cargado por `sincronizar_feriados`)."""

    queryset = DiaExcepcional.objects.all()
    serializer_class = DiaExcepcionalSerializer
    permission_classes = [IsAuthenticated, StrictDjangoModelPermissions]

    def get_queryset(self):
        organization_id = require_organization(self.request)
        return DiaExcepcional.objects.filter(
            Q(organization_id=organization_id) | Q(organization__isnull=True)
        )

    def perform_update(self, serializer):
        if serializer.instance.organization_id is None:
            raise PermissionDenied("El catálogo compartido de feriados no se edita por esta API.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.organization_id is None:
            raise PermissionDenied("El catálogo compartido de feriados no se borra por esta API.")
        instance.delete()

    @action(detail=False, methods=["post"], url_path="sincronizar-feriados")
    def sincronizar_feriados(self, request):
        """Trae/actualiza el catálogo compartido de feriados nacionales
        (`organization=None`) para el año actual y el siguiente. Pensado
        para llamarse una vez al entrar a la sección de días excepcionales
        del panel (no en cada request de la grilla): pega a una API externa,
        así que no conviene disparalo más seguido que eso. Es idempotente y
        nunca tira excepción — `services.sincronizar_feriados` atrapa
        cualquier error de red y devuelve False."""
        require_perm(request, "business_hours.view_diaexcepcional")
        anio_actual = timezone.localdate().year
        resultado = {
            anio: services.sincronizar_feriados(anio)
            for anio in (anio_actual, anio_actual + 1)
        }
        return Response({"anios": resultado})

    @action(detail=False, methods=["get", "post"])
    def grilla(self, request):
        """Editor de días puntuales (rango de fechas + tipo por día +, para
        Horario reducido, grilla de medias horas) — mismo patrón que
        `chatbot/templates/chatbot/calendario_excepciones.html`, adaptado a
        una sola organización por request."""
        organization_id = require_organization(request)
        slots = _slots_str()

        if request.method == "GET":
            desde = request.query_params.get("desde")
            hasta = request.query_params.get("hasta")
            if not desde or not hasta:
                raise ValidationError({"desde": "Se necesitan 'desde' y 'hasta' (YYYY-MM-DD)."})
            try:
                fecha_desde = dt.date.fromisoformat(desde)
                fecha_hasta = dt.date.fromisoformat(hasta)
            except ValueError:
                raise ValidationError({"desde": "Fecha inválida."})
            if fecha_hasta < fecha_desde:
                raise ValidationError({"hasta": "Debe ser posterior o igual a 'desde'."})
            if (fecha_hasta - fecha_desde).days > 31:
                raise ValidationError({"hasta": "El rango del editor es de máximo 31 días."})

            propias = {
                e.fecha: e
                for e in DiaExcepcional.objects.filter(
                    organization_id=organization_id, fecha__range=(fecha_desde, fecha_hasta),
                )
            }
            # Si la organización no cargó una excepción propia para esa fecha,
            # se trae la del catálogo compartido de feriados nacionales (si
            # hay) — mismo orden de precedencia que `services._rangos_del_dia`.
            compartidas = {
                e.fecha: e
                for e in DiaExcepcional.objects.filter(
                    organization__isnull=True, fecha__range=(fecha_desde, fecha_hasta),
                )
            }
            dias = []
            fecha = fecha_desde
            while fecha <= fecha_hasta:
                excepcion = propias.get(fecha)
                compartido = excepcion is None and fecha in compartidas
                if excepcion is None:
                    excepcion = compartidas.get(fecha)
                if excepcion is None:
                    dias.append({
                        "fecha": fecha.isoformat(), "tipo": "NORMAL", "celdas": [],
                        "descripcion": "", "compartido": False,
                    })
                else:
                    celdas = (
                        [h.strftime("%H:%M") for h in services.expandir_rango_a_horas(excepcion.hora_inicio, excepcion.hora_fin)]
                        if excepcion.tipo == DiaExcepcional.Tipo.HORARIO_REDUCIDO and excepcion.hora_inicio and excepcion.hora_fin
                        else []
                    )
                    dias.append({
                        "fecha": fecha.isoformat(), "tipo": excepcion.tipo, "celdas": celdas,
                        "descripcion": excepcion.descripcion, "compartido": compartido,
                    })
                fecha += dt.timedelta(days=1)
            return Response({"slots": slots, "dias": dias})

        require_perm(request, "business_hours.change_diaexcepcional")

        dias = request.data.get("dias")
        if not isinstance(dias, dict):
            raise ValidationError({"dias": "Se espera un objeto {fecha: {tipo, celdas}}."})

        tipos_validos = {choice for choice, _ in DiaExcepcional.Tipo.choices} | {"NORMAL"}
        a_borrar = []
        a_guardar = []
        for fecha_str, datos in dias.items():
            try:
                fecha = dt.date.fromisoformat(fecha_str)
            except ValueError:
                raise ValidationError({"dias": f"Fecha inválida: {fecha_str!r}"})
            tipo = (datos or {}).get("tipo")
            if tipo not in tipos_validos:
                raise ValidationError({"dias": f"Tipo inválido para {fecha_str}: {tipo!r}"})
            descripcion = ((datos or {}).get("descripcion") or "").strip()[:200]

            if tipo == "NORMAL":
                a_borrar.append(fecha)
                continue

            hora_inicio = hora_fin = None
            if tipo == DiaExcepcional.Tipo.HORARIO_REDUCIDO:
                celdas = (datos or {}).get("celdas") or []
                try:
                    horas = [dt.datetime.strptime(c, "%H:%M").time() for c in celdas]
                except ValueError:
                    raise ValidationError({"dias": f"Hora inválida en {fecha_str}."})
                rangos = services.merge_horas_a_rangos(horas)
                if not rangos:
                    raise ValidationError({"dias": f"Horario reducido de {fecha_str} necesita al menos una hora pintada."})
                hora_inicio, hora_fin = rangos[0]  # un solo rango contiguo por día (mismo límite que el modelo original)

            a_guardar.append((fecha, tipo, hora_inicio, hora_fin, descripcion))

        with transaction.atomic():
            if a_borrar:
                DiaExcepcional.objects.filter(organization_id=organization_id, fecha__in=a_borrar).delete()
            for fecha, tipo, hora_inicio, hora_fin, descripcion in a_guardar:
                DiaExcepcional.objects.update_or_create(
                    organization_id=organization_id, fecha=fecha,
                    defaults={
                        "tipo": tipo, "hora_inicio": hora_inicio, "hora_fin": hora_fin,
                        "descripcion": descripcion, "sincronizado": False,
                    },
                )

        return Response({"ok": True})


class TeamHorarioHabilView(RetrieveAPIView):
    """GET /api/core/teams/{id}/horario-habil/ — envuelve
    `esta_en_horario`/`proxima_apertura` para la organización del equipo."""

    serializer_class = HorarioHabilSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        require_perm(request, "business_hours.view_horarioatencion")
        team = get_object_or_404(Team, pk=kwargs["team_id"])
        if team.organization_id != request.user.organization_id:
            raise PermissionDenied("El equipo no pertenece a tu organización.")
        data = {
            "en_horario": services.esta_en_horario(team.organization_id),
            "proxima_apertura": services.proxima_apertura(team.organization_id),
        }
        return Response(self.get_serializer(data).data)
