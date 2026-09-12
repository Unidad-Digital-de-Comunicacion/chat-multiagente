from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from common.permissions import IsOrgAdmin
from common.viewsets import OrganizationScopedModelViewSet

from .models import User
from .serializers import MeSerializer, UserCreateSerializer, UserSerializer


class UserViewSet(OrganizationScopedModelViewSet):
    """ABM de usuarios de la organización. Sólo el rol Admin gestiona (alta,
    edición, baja); ver Fase 1 en docs/CONTEXTO_PROYECTO.md."""

    queryset = User.objects.all()
    permission_classes = [IsAuthenticated, IsOrgAdmin]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer


class MeView(RetrieveAPIView):
    """Perfil del usuario autenticado — disponible para cualquier rol."""

    serializer_class = MeSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
