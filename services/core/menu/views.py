from collections import defaultdict

from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.permissions import IsOrgAdminOrReadOnly
from common.viewsets import OrganizationScopedModelViewSet

from .models import MenuOpcion
from .serializers import MenuOpcionSerializer, MenuOpcionTreeSerializer


class MenuOpcionViewSet(OrganizationScopedModelViewSet):
    queryset = MenuOpcion.objects.select_related("parent", "team")
    serializer_class = MenuOpcionSerializer
    permission_classes = [IsAuthenticated, IsOrgAdminOrReadOnly]

    def perform_create(self, serializer):
        serializer.save(organization_id=self.request.user.organization_id, created_by=self.request.user)

    @action(detail=False, methods=["get"])
    def tree(self, request):
        """Árbol completo de la organización, anidado por `parent`, para el
        editor visual del Admin Panel (una sola query, sin N+1)."""
        opciones = list(self.get_queryset().filter(activo=True))
        por_padre = defaultdict(list)
        for opcion in opciones:
            por_padre[opcion.parent_id].append(opcion)

        raices = por_padre.get(None, [])
        serializer = MenuOpcionTreeSerializer(raices, many=True, context={"por_padre": por_padre})
        return Response(serializer.data)
