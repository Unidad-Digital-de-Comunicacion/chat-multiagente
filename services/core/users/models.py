from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from .managers import UserManager

AVATAR_THUMBNAIL_SIZE = (150, 150)


def avatar_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    return f"avatars/{instance.pk}.{ext}"


def avatar_thumbnail_upload_path(instance, filename):
    return f"avatars/thumbnails/{instance.pk}.jpg"


class User(AbstractBaseUser, PermissionsMixin):
    """Usuario de la plataforma. `email` es el identificador de login (no
    `username`: en un SaaS multi-tenant es más natural que dos organizaciones
    distintas no choquen por nombre de usuario). `organization` es null sólo
    para el superusuario de plataforma; todo usuario de negocio pertenece a
    una y sólo una organización.

    No hay un campo `role`: los permisos vienen enteramente de los grupos de
    Django (`PermissionsMixin.groups`), para que un usuario pueda pertenecer
    a más de uno a la vez (ej. Operador + Analista de datos). Ver
    `users.group_permissions` para qué puede hacer cada grupo."""

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    dni = models.CharField(
        max_length=20, unique=True, null=True, blank=True,
        help_text="Documento de identidad — opcional, se usa para 'recuperar usuario' (te "
                   "mandamos tu email registrado si el DNI coincide). Vacío = NULL, no cadena "
                   "vacía, para que no choquen dos cuentas sin DNI cargado bajo el mismo unique.",
    )
    avatar = models.ImageField(
        upload_to=avatar_upload_path, null=True, blank=True,
        help_text="La sube cada usuario ya recortada en cuadrado desde 'Mi perfil' (editor de "
                   "centrado/zoom del Admin Panel).",
    )
    avatar_thumbnail = models.ImageField(
        upload_to=avatar_thumbnail_upload_path, null=True, blank=True, editable=False,
        help_text="Miniatura de 150x150 generada automáticamente con Pillow a partir de `avatar` "
                   "(ver `User._regenerar_avatar_thumbnail`) — la usan los listados (tabla de "
                   "usuarios, topbar) para no bajar la imagen completa.",
    )
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE,
        null=True, blank=True, related_name="users",
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    must_change_password = models.BooleanField(
        default=False,
        help_text="True después de que un Admin le resetea la contraseña — el front lo obliga a "
                   "elegir una propia antes de dejarlo usar el resto del panel.",
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email

    def save(self, *args, **kwargs):
        avatar_anterior = None
        if self.pk:
            avatar_anterior = User.objects.filter(pk=self.pk).values_list("avatar", flat=True).first()
        super().save(*args, **kwargs)
        avatar_actual = self.avatar.name if self.avatar else None
        if avatar_actual != avatar_anterior:
            if avatar_anterior:
                # Storage por default no pisa archivos con el mismo nombre (le agrega un
                # sufijo random) — borramos el anterior a mano para no acumular huérfanos
                # y mantener siempre `avatars/<pk>.<ext>` como ruta estable.
                self.avatar.storage.delete(avatar_anterior)
            self._regenerar_avatar_thumbnail()

    def _regenerar_avatar_thumbnail(self):
        """Genera con Pillow una miniatura de `avatar` para los listados
        (tabla de Usuarios, avatar del topbar) sin tener que bajar la imagen
        completa. El frontend ya sube `avatar` pre-recortado en cuadrado
        (editor de centrado/zoom de 'Mi perfil'), así que acá sólo reduce el
        tamaño — no vuelve a recortar."""
        from io import BytesIO

        from django.core.files.base import ContentFile
        from PIL import Image, ImageOps

        if self.avatar_thumbnail:
            self.avatar_thumbnail.delete(save=False)
        if not self.avatar:
            User.objects.filter(pk=self.pk).update(avatar_thumbnail=None)
            return
        with self.avatar.open("rb") as archivo:
            imagen = ImageOps.exif_transpose(Image.open(archivo)).convert("RGB")
            imagen.thumbnail(AVATAR_THUMBNAIL_SIZE, Image.LANCZOS)
            buffer = BytesIO()
            imagen.save(buffer, format="JPEG", quality=85)
        self.avatar_thumbnail.save(f"{self.pk}.jpg", ContentFile(buffer.getvalue()), save=False)
        models.Model.save(self, update_fields=["avatar_thumbnail"])

    class Meta:
        ordering = ["email"]
