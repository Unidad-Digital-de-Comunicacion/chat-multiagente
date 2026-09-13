from collections import defaultdict

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from common.permissions import StrictDjangoModelPermissions, require_organization, require_perm
from common.viewsets import OrganizationScopedModelViewSet

from .models import MenuOpcion
from .serializers import MenuOpcionSerializer, MenuOpcionTreeSerializer


class MenuOpcionViewSet(OrganizationScopedModelViewSet):
    """`menu.view_menuopcion`/`add_`/`change_`/`delete_menuopcion` (sólo
    administradores hoy) — ver `users.group_permissions`."""

    queryset = MenuOpcion.objects.select_related("parent", "team")
    serializer_class = MenuOpcionSerializer
    permission_classes = [IsAuthenticated, StrictDjangoModelPermissions]

    def perform_create(self, serializer):
        serializer.save(organization_id=self.request.user.organization_id, created_by=self.request.user)

    @action(detail=False, methods=["get"])
    def tree(self, request):
        """Árbol completo de la organización, anidado por `parent`, para el
        editor visual del Admin Panel (una sola query, sin N+1)."""
        require_perm(request, "menu.view_menuopcion")
        opciones = list(self.get_queryset().filter(activo=True))
        por_padre = defaultdict(list)
        for opcion in opciones:
            por_padre[opcion.parent_id].append(opcion)

        raices = por_padre.get(None, [])
        serializer = MenuOpcionTreeSerializer(raices, many=True, context={"por_padre": por_padre})
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def reordenar(self, request):
        """Reordena y/o reparenta de un saque un grupo de nodos hermanos —
        mismo contrato que `chatbot/static/js/chatbot_menu.js::guardarOrden`
        (portado): el cliente manda `parent_id` (o null para la raíz) y la
        lista COMPLETA y ya ordenada de ids que van a quedar como hijos
        directos de ese padre después del drag-and-drop."""
        require_perm(request, "menu.change_menuopcion")

        organization_id = require_organization(request)
        parent_id = request.data.get("parent_id")
        orden = request.data.get("orden")
        if not isinstance(orden, list) or not orden:
            raise ValidationError({"orden": "Se espera una lista de ids no vacía."})

        parent = None
        if parent_id is not None:
            parent = get_object_or_404(MenuOpcion, pk=parent_id, organization_id=organization_id)
            if parent.tipo != MenuOpcion.Tipo.SUBMENU:
                raise ValidationError({"parent_id": "El padre debe ser de tipo Menú (SUBMENU)."})

        nodos = list(MenuOpcion.objects.filter(organization_id=organization_id, pk__in=orden))
        if len(nodos) != len(set(orden)):
            raise ValidationError({"orden": "Alguno de los ids no existe en tu organización."})
        ids_movidos = {n.pk for n in nodos}

        if parent is not None:
            actual = parent
            while actual is not None:
                if actual.pk in ids_movidos:
                    raise ValidationError({"parent_id": "No se puede mover un menú dentro de sí mismo."})
                actual = actual.parent

        with transaction.atomic():
            for index, node_id in enumerate(orden):
                MenuOpcion.objects.filter(pk=node_id, organization_id=organization_id).update(
                    parent_id=parent_id, orden=index,
                )

        return Response({"ok": True})
