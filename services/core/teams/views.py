from rest_framework.permissions import IsAuthenticated

from common.permissions import StrictDjangoModelPermissions
from common.viewsets import OrganizationScopedModelViewSet

from .models import Team
from .serializers import TeamSerializer


class TeamViewSet(OrganizationScopedModelViewSet):
    """`teams.view_team` (administradores + operadores) para leer,
    `teams.add_team`/`change_team`/`delete_team` (sólo administradores) para
    escribir — ver `users.group_permissions`."""

    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    permission_classes = [IsAuthenticated, StrictDjangoModelPermissions]
