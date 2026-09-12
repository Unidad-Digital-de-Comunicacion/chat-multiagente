from rest_framework.permissions import IsAuthenticated

from common.permissions import IsOrgAdminOrReadOnly
from common.viewsets import OrganizationScopedModelViewSet

from .models import Team
from .serializers import TeamSerializer


class TeamViewSet(OrganizationScopedModelViewSet):
    """Cualquier usuario autenticado de la organización puede ver los
    equipos (los necesita, por ejemplo, para elegir a cuál deriva un nodo de
    menú); sólo Admin los crea/edita/borra."""

    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    permission_classes = [IsAuthenticated, IsOrgAdminOrReadOnly]
