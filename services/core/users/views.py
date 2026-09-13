import secrets

from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import StrictDjangoModelPermissions, require_perm
from common.viewsets import OrganizationScopedModelViewSet

from .models import User
from .serializers import GroupSerializer, MeSerializer, MyProfileSerializer, UserCreateSerializer, UserSerializer


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
