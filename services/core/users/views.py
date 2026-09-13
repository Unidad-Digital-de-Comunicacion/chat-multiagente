import secrets

from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsPlatformSuperuser, StrictDjangoModelPermissions, require_perm
from common.soft_delete import marcar_eliminado, restaurar_eliminado
from common.viewsets import OrganizationScopedModelViewSet

from .models import User
from .serializers import (
    GroupSerializer, MeSerializer, MyProfileSerializer, PlatformUserCreateSerializer,
    PlatformUserSerializer, UserCreateSerializer, UserSerializer,
)


class PlatformUserViewSet(viewsets.ModelViewSet):
    """Usuarios de TODAS las organizaciones — sección "Plataforma" del Admin
    Panel, sólo el superusuario real (`IsPlatformSuperuser`, mismo motivo
    que `organizations.PlatformOrganizationViewSet`: `users.view_user`/
    `change_user`/etc. son los mismos permisos que ya tiene
    `administradores` para su propia organización). `?organization=<id>`
    filtra el listado por organización, para "usuarios divididos por cada
    organización"; sin el filtro, devuelve todos."""

    queryset = User.objects.all().order_by("email")
    permission_classes = [IsPlatformSuperuser]

    def get_serializer_class(self):
        if self.action == "create":
            return PlatformUserCreateSerializer
        return PlatformUserSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        organization_id = self.request.query_params.get("organization")
        if organization_id == "null":
            qs = qs.filter(organization_id=None)
        elif organization_id:
            qs = qs.filter(organization_id=organization_id)
        if self.request.query_params.get("incluir_eliminados") != "1":
            qs = qs.filter(deleted_at__isnull=True)
        return qs

    def perform_destroy(self, instance):
        """`DELETE` es un soft delete (`common.soft_delete`) — nunca se
        borra la fila, se marca `deleted_at` y `is_active=False`. Se
        deshace con la action `restaurar`."""
        marcar_eliminado(instance)

    @action(detail=True, methods=["post"])
    def restaurar(self, request, pk=None):
        """Deshace el soft delete. Busca por fuera de `get_queryset` (que
        excluye eliminados por default) — si no, nunca encontraría al
        usuario que justamente hay que restaurar."""
        user = get_object_or_404(User, pk=pk)
        restaurar_eliminado(user)
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        """Igual que `UserViewSet.reset_password` pero sin scoping de
        organización — acá el superusuario puede resetear la de cualquier
        usuario de cualquier organización."""
        user = self.get_object()
        temporal = secrets.token_urlsafe(9)
        user.set_password(temporal)
        user.must_change_password = True
        user.save(update_fields=["password", "must_change_password"])
        return Response({"password_temporal": temporal})


class UserViewSet(OrganizationScopedModelViewSet):
    """ABM de usuarios de la organización. Gestionarlos (ver/crear/editar/
    borrar) requiere el permiso Django correspondiente
    (`users.view_user`/`add_user`/`change_user`/`delete_user`), que hoy sólo
    tienen los grupos administradores/superusuarios — ver
    `users.group_permissions`. Asignar el grupo de un usuario se hace acá
    mismo (PATCH `groups`), ya que requiere `users.change_user`."""

    queryset = User.objects.all()
    permission_classes = [IsAuthenticated, StrictDjangoModelPermissions]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("incluir_eliminados") != "1":
            qs = qs.filter(deleted_at__isnull=True)
        return qs

    def perform_destroy(self, instance):
        """`DELETE` es un soft delete (`common.soft_delete`) — nunca se
        borra la fila, se marca `deleted_at` y `is_active=False`. Se
        deshace con la action `restaurar`."""
        marcar_eliminado(instance)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def restaurar(self, request, pk=None):
        """Deshace el soft delete de un usuario de la propia organización.
        Busca por fuera de `get_queryset` (excluye eliminados por default,
        si no nunca encontraría al usuario a restaurar) pero sigue scopeado
        a la organización del Admin — no puede restaurar el de otra."""
        require_perm(request, "users.change_user")
        user = get_object_or_404(User, pk=pk, organization_id=request.user.organization_id)
        restaurar_eliminado(user)
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=["post"], url_path="reset-password", permission_classes=[IsAuthenticated])
    def reset_password(self, request, pk=None):
        """Resetea la contraseña de un usuario de la propia organización
        (el scoping lo da `get_object` → `get_queryset` de
        `OrganizationScopedModelViewSet`, igual que cualquier otro detalle:
        un Admin no puede resetear la de otra organización). Genera una
        contraseña temporal aleatoria, la devuelve UNA sola vez en la
        respuesta (no se guarda en texto plano en ningún lado) para que el
        Admin se la pase al usuario por otro medio, y marca
        `must_change_password` para que el front lo obligue a elegir la
        suya propia en el próximo login."""
        require_perm(request, "users.change_user")
        user = self.get_object()
        temporal = secrets.token_urlsafe(9)
        user.set_password(temporal)
        user.must_change_password = True
        user.save(update_fields=["password", "must_change_password"])
        return Response({"password_temporal": temporal})


class MeView(RetrieveUpdateAPIView):
    """GET: perfil + contrato de autorización (`MeSerializer`, sólo lectura).
    PATCH/PUT: el propio usuario edita sus datos personales
    (`MyProfileSerializer` — nombre, email, DNI, avatar; nunca grupos ni
    organización). `avatar` viaja como `multipart/form-data`, por eso los
    parsers explícitos (el resto de la API sólo necesita JSON)."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ("PATCH", "PUT"):
            return MyProfileSerializer
        return MeSerializer


class ChangeMyPasswordView(APIView):
    """POST /api/core/users/me/cambiar-password/ — el propio usuario cambia
    su contraseña (pide la actual, a diferencia del reset de Admin). Es el
    paso obligatorio después de que un Admin le reseteó la contraseña
    (`must_change_password=True`), pero cualquiera puede usarlo en cualquier
    momento para cambiar la suya."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        actual = request.data.get("current_password") or ""
        nueva = request.data.get("new_password") or ""
        if not request.user.check_password(actual):
            raise ValidationError({"current_password": ["La contraseña actual no es correcta."]})
        try:
            validate_password(nueva, user=request.user)
        except DjangoValidationError as exc:
            raise ValidationError({"new_password": list(exc.messages)})
        request.user.set_password(nueva)
        request.user.must_change_password = False
        request.user.save(update_fields=["password", "must_change_password"])
        return Response({"ok": True})


class GroupListView(ListAPIView):
    """Los 5 grupos de la plataforma, para que el Admin Panel arme el
    selector al asignarle grupo(s) a un usuario. `auth.view_group` (sección
    `users.group_permissions`). Sin paginar a propósito: son siempre 5, el
    Admin Panel espera un array plano (`Group[]`), no el sobre paginado
    `{count, results}` que usa el resto de la API."""

    queryset = Group.objects.all().order_by("name")
    pagination_class = None
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated, StrictDjangoModelPermissions]
