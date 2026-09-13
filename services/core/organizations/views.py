from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.permissions import IsPlatformSuperuser, StrictDjangoModelPermissions, require_organization
from common.soft_delete import marcar_eliminado, restaurar_eliminado

from .models import Organization
from .serializers import OrganizationSerializer, PlatformOrganizationSerializer


class PlatformOrganizationViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin,
    mixins.CreateModelMixin, mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Administración de TODAS las organizaciones — sección "Plataforma" del
    Admin Panel, sólo para el superusuario real de plataforma
    (`common.permissions.IsPlatformSuperuser`; ver esa clase para por qué
    esto no alcanza con el permiso Django estándar `organizations.*`, que
    también tiene `administradores` para la suya propia).

    `DELETE` es un soft delete (`common.soft_delete`, nunca se borra la fila
    de la organización NI las de sus usuarios) que además desactiva/marca
    como eliminados a TODOS sus usuarios de un saque — "eliminar una
    organización entera, con sus usuarios". `?incluir_eliminadas=1` las trae
    de vuelta en el listado (por default quedan afuera); la action
    `restaurar` deshace todo (la organización y los usuarios que estaban
    activos antes de que se eliminara junto con ella — uno que ya estaba
    eliminado a mano de antes sigue eliminado)."""

    queryset = Organization.objects.all()
    serializer_class = PlatformOrganizationSerializer
    permission_classes = [IsPlatformSuperuser]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("incluir_eliminadas") != "1":
            qs = qs.filter(deleted_at__isnull=True)
        return qs

    def perform_destroy(self, instance):
        marcar_eliminado(instance)
        instance.users.filter(deleted_at__isnull=True).update(
            deleted_at=instance.deleted_at, is_active=False,
        )

    @action(detail=True, methods=["post"])
    def restaurar(self, request, pk=None):
        organization = get_object_or_404(Organization, pk=pk)
        organization.users.filter(deleted_at=organization.deleted_at).update(deleted_at=None, is_active=True)
        restaurar_eliminado(organization)
        return Response(self.get_serializer(organization).data)


class MyOrganizationView(RetrieveUpdateAPIView):
    """La organización del usuario autenticado. No hay alta/baja vía API:
    una organización nueva se provisiona fuera de este servicio (onboarding
    comercial), no de forma self-service.

    `queryset` está para que `StrictDjangoModelPermissions` sepa de qué
    modelo se trata (GET necesita `view_organization`, PATCH necesita
    `change_organization`) aunque el objeto en sí lo resuelva `get_object`."""

    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated, StrictDjangoModelPermissions]

    def get_object(self):
        return Organization.objects.get(pk=require_organization(self.request))
