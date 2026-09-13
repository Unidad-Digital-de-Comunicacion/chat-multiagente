from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .group_permissions import GRUPOS_RESERVADOS_A_PLATAFORMA
from .models import User


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["id", "name"]


def _validar_grupos_asignables(request, groups):
    """Un Admin de organización (no-staff) no puede meter a nadie en un
    grupo de alcance de plataforma (ej. "superusuarios") — eso sólo se hace
    desde /admin/ (sección 'administradores, solo desde el front' de la
    consigna)."""
    if request and not request.user.is_staff:
        reservados = {g.name for g in groups} & GRUPOS_RESERVADOS_A_PLATAFORMA
        if reservados:
            raise serializers.ValidationError(
                f"Sólo se asignan desde /admin/: {', '.join(sorted(reservados))}"
            )
    return groups


def _file_url(fieldfile, request):
    """`fieldfile.url` sólo es una ruta relativa a MEDIA_URL — hay que
    convertirla en absoluta con el host de Core, porque el Admin Panel corre
    en otro origen/puerto (`VITE_CORE_API_URL`) y no sirve nada en `/media/`
    él mismo. El `ImageField` real de DRF (`MyProfileSerializer.avatar`) ya
    hace esto solo vía `request.build_absolute_uri`; acá lo repetimos a mano
    para los `SerializerMethodField` de avatar/avatar_thumbnail."""
    if not fieldfile:
        return None
    url = fieldfile.url
    return request.build_absolute_uri(url) if request else url


def _validar_dni_unico(value, instance):
    """Vacío → None (no cadena vacía, para no chocar el `unique` entre dos
    cuentas sin DNI cargado). Si viene cargado, chequea que no sea el de otra
    cuenta — el `unique=True` del modelo es la garantía real ante una carrera,
    esto es sólo para devolver un 400 legible en el caso normal."""
    value = (value or "").strip() or None
    if value is None:
        return None
    qs = User.objects.filter(dni=value)
    if instance is not None:
        qs = qs.exclude(pk=instance.pk)
    if qs.exists():
        raise serializers.ValidationError("Ese DNI ya está registrado en otra cuenta.")
    return value


class UserSerializer(serializers.ModelSerializer):
    """La usa el ViewSet de administración (`UserViewSet`): un Admin puede
    ver/editar cualquier usuario de su organización, incluido subirle/
    reemplazarle el avatar (ej. para dejarlo cargado antes de que la persona
    inicie sesión por primera vez) además de lo que cada uno edita de su
    propio perfil (`MyProfileSerializer`)."""

    groups = serializers.PrimaryKeyRelatedField(many=True, queryset=Group.objects.all(), required=False)
    group_names = serializers.SerializerMethodField()
    avatar = serializers.ImageField(required=False, allow_null=True)
    avatar_thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "dni", "avatar", "avatar_thumbnail",
            "groups", "group_names", "organization", "is_active", "date_joined", "must_change_password",
        ]
        read_only_fields = ["id", "organization", "date_joined", "must_change_password"]

    def get_group_names(self, obj):
        return list(obj.groups.values_list("name", flat=True))

    def get_avatar_thumbnail(self, obj):
        return _file_url(obj.avatar_thumbnail, self.context.get("request"))

    def validate_groups(self, groups):
        return _validar_grupos_asignables(self.context.get("request"), groups)

    def validate_dni(self, value):
        return _validar_dni_unico(value, self.instance)


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    groups = serializers.PrimaryKeyRelatedField(many=True, queryset=Group.objects.all(), required=False)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "dni", "password", "groups", "is_active"]

    def validate_groups(self, groups):
        return _validar_grupos_asignables(self.context.get("request"), groups)

    def validate_dni(self, value):
        return _validar_dni_unico(value, None)

    def create(self, validated_data):
        password = validated_data.pop("password")
        groups = validated_data.pop("groups", [])
        # `organization` la fija el ViewSet (OrganizationScopedModelViewSet),
        # nunca el body de la request.
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        if groups:
            user.groups.set(groups)
        return user


class MyProfileSerializer(serializers.ModelSerializer):
    """Edición de datos personales por el propio usuario: nombre, email,
    DNI y avatar — nunca grupos/permisos/organización, eso es cosa de un
    Admin (`UserSerializer`)."""

    avatar = serializers.ImageField(required=False, allow_null=True)
    avatar_thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "dni", "avatar", "avatar_thumbnail"]
        read_only_fields = ["avatar_thumbnail"]

    def get_avatar_thumbnail(self, obj):
        return _file_url(obj.avatar_thumbnail, self.context.get("request"))

    def validate_dni(self, value):
        return _validar_dni_unico(value, self.instance)


class MeSerializer(serializers.ModelSerializer):
    """Perfil del usuario autenticado + el contrato de autorización para el
    frontend: `permissions` es la lista real de permisos Django efectivos
    (unión de todos sus grupos). El Admin Panel decide qué mostrar/ocultar
    consultando esta lista — nunca hardcodeando un nombre de rol — para que
    la fuente de verdad de "qué puede hacer" sea siempre el backend."""

    organization_id = serializers.IntegerField(read_only=True)
    groups = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    avatar_thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "dni", "avatar", "avatar_thumbnail",
            "groups", "permissions", "organization_id", "is_staff", "is_superuser",
            "must_change_password",
        ]
        read_only_fields = fields

    def get_groups(self, obj):
        return list(obj.groups.values_list("name", flat=True))

    def get_permissions(self, obj):
        return sorted(obj.get_all_permissions())

    def get_avatar(self, obj):
        return _file_url(obj.avatar, self.context.get("request"))

    def get_avatar_thumbnail(self, obj):
        return _file_url(obj.avatar_thumbnail, self.context.get("request"))
