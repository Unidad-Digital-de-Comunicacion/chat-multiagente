from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated

from common.permissions import IsOrgAdminOrReadOnly

from .models import Organization
from .serializers import OrganizationSerializer


class MyOrganizationView(RetrieveUpdateAPIView):
    """La organización del usuario autenticado. No hay alta/baja vía API:
    una organización nueva se provisiona fuera de este servicio (onboarding
    comercial), no de forma self-service."""

    serializer_class = OrganizationSerializer
    permission_classes = [IsAuthenticated, IsOrgAdminOrReadOnly]

    def get_object(self):
        return Organization.objects.get(pk=self.request.user.organization_id)
