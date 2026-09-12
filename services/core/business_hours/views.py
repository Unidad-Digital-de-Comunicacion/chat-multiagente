from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.permissions import IsOrgAdminOrReadOnly
from common.viewsets import OrganizationScopedModelViewSet
from teams.models import Team

from . import services
from .models import DiaExcepcional, HorarioAtencion
from .serializers import (
    DiaExcepcionalSerializer, HorarioAtencionSerializer, HorarioHabilSerializer,
)


class HorarioAtencionViewSet(OrganizationScopedModelViewSet):
    queryset = HorarioAtencion.objects.all()
    serializer_class = HorarioAtencionSerializer
    permission_classes = [IsAuthenticated, IsOrgAdminOrReadOnly]


class DiaExcepcionalViewSet(OrganizationScopedModelViewSet):
    """Además de sus propias excepciones, cada organización ve (sin poder
    editar) el catálogo compartido de feriados nacionales
    (`organization=None`, cargado por `sincronizar_feriados`)."""

    queryset = DiaExcepcional.objects.all()
    serializer_class = DiaExcepcionalSerializer
    permission_classes = [IsAuthenticated, IsOrgAdminOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        return DiaExcepcional.objects.filter(
            Q(organization_id=user.organization_id) | Q(organization__isnull=True)
        )

    def perform_update(self, serializer):
        if serializer.instance.organization_id is None:
            raise PermissionDenied("El catálogo compartido de feriados no se edita por esta API.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.organization_id is None:
            raise PermissionDenied("El catálogo compartido de feriados no se borra por esta API.")
        instance.delete()


class TeamHorarioHabilView(RetrieveAPIView):
    """GET /api/core/teams/{id}/horario-habil/ — envuelve
    `esta_en_horario`/`proxima_apertura` para la organización del equipo."""

    serializer_class = HorarioHabilSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        team = get_object_or_404(Team, pk=kwargs["team_id"])
        if team.organization_id != request.user.organization_id and not request.user.is_superuser:
            raise PermissionDenied("El equipo no pertenece a tu organización.")
        data = {
            "en_horario": services.esta_en_horario(team.organization_id),
            "proxima_apertura": services.proxima_apertura(team.organization_id),
        }
        return Response(self.get_serializer(data).data)
