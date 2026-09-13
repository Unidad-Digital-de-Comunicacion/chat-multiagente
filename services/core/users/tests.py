from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from common.test_utils import authenticated_client, make_organization, make_user
from users.models import User


def _imagen_de_prueba(color=(255, 0, 0), size=(300, 300)):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="JPEG")
    buffer.seek(0)
    return SimpleUploadedFile("avatar.jpg", buffer.read(), content_type="image/jpeg")


class UserManagerTests(TestCase):
    def test_create_user_requiere_email(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password="x")

    def test_create_superuser_sin_organizacion(self):
        superuser = User.objects.create_superuser(email="plataforma@chatplatform.test", password="Contrasena-123")
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)
        self.assertIsNone(superuser.organization_id)


class UserViewSetTests(TestCase):
    def setUp(self):
        self.org_a = make_organization(name="Org A", slug="org-a")
        self.org_b = make_organization(name="Org B", slug="org-b")
        self.admin_a = make_user(self.org_a, groups=["administradores"])
        self.operador_a = make_user(self.org_a, groups=["operadores"])
        self.admin_b = make_user(self.org_b, groups=["administradores"])
        self.list_url = reverse("user-list")

    def test_admin_solo_ve_usuarios_de_su_organizacion(self):
        response = authenticated_client(self.admin_a).get(self.list_url)
        emails = {u["email"] for u in response.data["results"]}
        self.assertIn(self.admin_a.email, emails)
        self.assertIn(self.operador_a.email, emails)
        self.assertNotIn(self.admin_b.email, emails)

    def test_operador_no_puede_listar_usuarios(self):
        response = authenticated_client(self.operador_a).get(self.list_url)
        self.assertEqual(response.status_code, 403)

    def test_admin_no_puede_ver_un_usuario_de_otra_organizacion_por_id(self):
        # admin_a SÍ tiene el permiso Django `users.view_user` (mismo grupo
        # que admin_b) — el aislamiento tiene que venir del scoping por
        # organización, no del permiso, que es global. Por eso da 404 (no
        # está en su queryset) y no 403.
        url = reverse("user-detail", args=[self.admin_b.id])
        response = authenticated_client(self.admin_a).get(url)
        self.assertEqual(response.status_code, 404)

    def test_admin_no_puede_editar_un_usuario_de_otra_organizacion_por_id(self):
        url = reverse("user-detail", args=[self.admin_b.id])
        response = authenticated_client(self.admin_a).patch(url, {"is_active": False})
        self.assertEqual(response.status_code, 404)
        self.admin_b.refresh_from_db()
        self.assertTrue(self.admin_b.is_active)

    def test_admin_no_puede_borrar_un_usuario_de_otra_organizacion_por_id(self):
        url = reverse("user-detail", args=[self.admin_b.id])
        response = authenticated_client(self.admin_a).delete(url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(User.objects.filter(pk=self.admin_b.id).exists())

    def test_admin_crea_usuario_queda_en_su_propia_organizacion(self):
        payload = {"email": "nuevo@org-a.test", "password": "Contrasena-123"}
        response = authenticated_client(self.admin_a).post(self.list_url, payload)
        self.assertEqual(response.status_code, 201, response.data)
        nuevo = User.objects.get(email="nuevo@org-a.test")
        self.assertEqual(nuevo.organization_id, self.org_a.id)

    def test_admin_no_puede_forzar_organizacion_ajena_en_el_body(self):
        payload = {
            "email": "otro@org-a.test", "password": "Contrasena-123", "organization": self.org_b.id,
        }
        response = authenticated_client(self.admin_a).post(self.list_url, payload)
        self.assertEqual(response.status_code, 201, response.data)
        nuevo = User.objects.get(email="otro@org-a.test")
        self.assertEqual(nuevo.organization_id, self.org_a.id)

    def test_admin_no_puede_asignar_el_grupo_superusuarios(self):
        from django.contrib.auth.models import Group

        from users.group_permissions import sync_groups

        sync_groups()
        superusuarios = Group.objects.get(name="superusuarios")
        payload = {
            "email": "colado@org-a.test", "password": "Contrasena-123", "groups": [superusuarios.id],
        }
        response = authenticated_client(self.admin_a).post(self.list_url, payload)
        self.assertEqual(response.status_code, 400)

    def test_admin_puede_agregar_un_usuario_a_mas_de_un_grupo(self):
        from django.contrib.auth.models import Group

        payload = {
            "email": "multi@org-a.test", "password": "Contrasena-123",
            "groups": list(Group.objects.filter(name__in=["operadores", "analistas_datos"]).values_list("id", flat=True)),
        }
        response = authenticated_client(self.admin_a).post(self.list_url, payload)
        self.assertEqual(response.status_code, 201, response.data)
        nuevo = User.objects.get(email="multi@org-a.test")
        self.assertEqual(
            set(nuevo.groups.values_list("name", flat=True)), {"operadores", "analistas_datos"},
        )

    def test_admin_resetea_la_contrasena_de_un_usuario_de_su_organizacion(self):
        url = reverse("user-reset-password", args=[self.operador_a.id])
        response = authenticated_client(self.admin_a).post(url)
        self.assertEqual(response.status_code, 200, response.data)
        temporal = response.data["password_temporal"]

        self.operador_a.refresh_from_db()
        self.assertTrue(self.operador_a.check_password(temporal))
        self.assertTrue(self.operador_a.must_change_password)

        # la contraseña vieja ya no sirve para loguear
        login = self.client.post(reverse("auth-login"), {"email": self.operador_a.email, "password": "Contrasena-123"})
        self.assertEqual(login.status_code, 401)
        login = self.client.post(reverse("auth-login"), {"email": self.operador_a.email, "password": temporal})
        self.assertEqual(login.status_code, 200)

    def test_admin_no_puede_resetear_la_contrasena_de_otra_organizacion(self):
        url = reverse("user-reset-password", args=[self.admin_b.id])
        response = authenticated_client(self.admin_a).post(url)
        self.assertEqual(response.status_code, 404)

    def test_operador_no_puede_resetear_contrasenas(self):
        url = reverse("user-reset-password", args=[self.admin_a.id])
        response = authenticated_client(self.operador_a).post(url)
        self.assertEqual(response.status_code, 403)

    def test_admin_edita_datos_de_un_usuario_de_su_organizacion(self):
        # El caso que explícitamente pidió revisarse: alta ya está cubierto
        # arriba (test_admin_crea_usuario_...); esto cubre la EDICIÓN.
        url = reverse("user-detail", args=[self.operador_a.id])
        response = authenticated_client(self.admin_a).patch(url, {
            "first_name": "Juan", "last_name": "Pérez", "dni": "30111222", "is_active": False,
        })
        self.assertEqual(response.status_code, 200, response.data)
        self.operador_a.refresh_from_db()
        self.assertEqual(self.operador_a.first_name, "Juan")
        self.assertEqual(self.operador_a.last_name, "Pérez")
        self.assertEqual(self.operador_a.dni, "30111222")
        self.assertFalse(self.operador_a.is_active)

    def test_admin_puede_subirle_el_avatar_a_otro_usuario(self):
        url = reverse("user-detail", args=[self.operador_a.id])
        response = authenticated_client(self.admin_a).patch(
            url, {"avatar": _imagen_de_prueba()}, format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["avatar"].startswith("http"))
        self.assertTrue(response.data["avatar_thumbnail"].startswith("http"))
        self.operador_a.refresh_from_db()
        self.assertTrue(self.operador_a.avatar)
        self.assertTrue(self.operador_a.avatar_thumbnail)

    def test_admin_crea_usuario_con_dni(self):
        payload = {"email": "condni@org-a.test", "password": "Contrasena-123", "dni": "40222333"}
        response = authenticated_client(self.admin_a).post(self.list_url, payload)
        self.assertEqual(response.status_code, 201, response.data)
        nuevo = User.objects.get(email="condni@org-a.test")
        self.assertEqual(nuevo.dni, "40222333")

    def test_no_puede_crear_dos_usuarios_con_el_mismo_dni(self):
        authenticated_client(self.admin_a).post(
            self.list_url, {"email": "uno@org-a.test", "password": "Contrasena-123", "dni": "40222333"},
        )
        response = authenticated_client(self.admin_a).post(
            self.list_url, {"email": "dos@org-a.test", "password": "Contrasena-123", "dni": "40222333"},
        )
        self.assertEqual(response.status_code, 400)

    def test_dos_usuarios_pueden_tener_el_dni_vacio(self):
        # El `unique=True` del modelo es sobre NULL, no sobre '' — dos altas
        # sin DNI cargado no deberían chocar entre sí.
        r1 = authenticated_client(self.admin_a).post(
            self.list_url, {"email": "sindni1@org-a.test", "password": "Contrasena-123"},
        )
        r2 = authenticated_client(self.admin_a).post(
            self.list_url, {"email": "sindni2@org-a.test", "password": "Contrasena-123"},
        )
        self.assertEqual(r1.status_code, 201, r1.data)
        self.assertEqual(r2.status_code, 201, r2.data)


class MyProfileViewTests(TestCase):
    """PATCH /api/core/users/me/ — el propio usuario edita sus datos
    personales (nombre, email, DNI, avatar). Nunca toca grupos/organización."""

    def setUp(self):
        self.org = make_organization()
        self.user = make_user(self.org, groups=["operadores"], email="perfil@org.test")
        self.url = reverse("user-me")

    def test_edita_nombre_y_apellido(self):
        response = authenticated_client(self.user).patch(self.url, {"first_name": "Ana", "last_name": "Gómez"})
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Ana")
        self.assertEqual(self.user.last_name, "Gómez")

    def test_edita_su_propio_email(self):
        response = authenticated_client(self.user).patch(self.url, {"email": "nuevo@org.test"})
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "nuevo@org.test")

    def test_no_puede_repetir_el_email_de_otra_cuenta(self):
        make_user(self.org, groups=["operadores"], email="ocupado@org.test")
        response = authenticated_client(self.user).patch(self.url, {"email": "ocupado@org.test"})
        self.assertEqual(response.status_code, 400)

    def test_carga_su_dni(self):
        response = authenticated_client(self.user).patch(self.url, {"dni": "35444555"})
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.dni, "35444555")

    def test_no_puede_repetir_el_dni_de_otra_cuenta(self):
        make_user(self.org, groups=["operadores"], email="otro@org.test", dni="99888777")
        response = authenticated_client(self.user).patch(self.url, {"dni": "99888777"})
        self.assertEqual(response.status_code, 400)

    def test_no_puede_tocar_sus_propios_grupos_ni_organizacion(self):
        response = authenticated_client(self.user).patch(self.url, {"groups": [], "is_active": False})
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.groups.filter(name="operadores").exists())
        self.assertTrue(self.user.is_active)

    def test_get_sigue_devolviendo_el_contrato_de_permisos(self):
        response = authenticated_client(self.user).get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("permissions", response.data)
        self.assertIn("groups", response.data)

    def test_sube_avatar_y_genera_miniatura_con_pillow(self):
        response = authenticated_client(self.user).patch(
            self.url, {"avatar": _imagen_de_prueba()}, format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.data)
        # Las URLs tienen que ser absolutas (el Admin Panel corre en otro
        # origen/puerto que Core, así que una ruta relativa no serviría).
        self.assertTrue(response.data["avatar"].startswith("http"))
        self.assertTrue(response.data["avatar_thumbnail"].startswith("http"))

        self.user.refresh_from_db()
        self.assertTrue(self.user.avatar)
        self.assertTrue(self.user.avatar_thumbnail)
        with self.user.avatar_thumbnail.open("rb") as f:
            miniatura = Image.open(f)
            miniatura.load()
        self.assertLessEqual(miniatura.width, 150)
        self.assertLessEqual(miniatura.height, 150)

    def test_reemplazar_el_avatar_borra_el_archivo_anterior(self):
        authenticated_client(self.user).patch(self.url, {"avatar": _imagen_de_prueba()}, format="multipart")
        self.user.refresh_from_db()
        storage = self.user.avatar.storage
        nombre_anterior = self.user.avatar.name

        authenticated_client(self.user).patch(
            self.url, {"avatar": _imagen_de_prueba(color=(0, 255, 0))}, format="multipart",
        )
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.avatar.name, nombre_anterior)
        self.assertFalse(storage.exists(nombre_anterior))

    def test_me_get_tambien_devuelve_avatar_absoluto_despues_de_subirlo(self):
        authenticated_client(self.user).patch(self.url, {"avatar": _imagen_de_prueba()}, format="multipart")
        response = authenticated_client(self.user).get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["avatar"].startswith("http"))
        self.assertTrue(response.data["avatar_thumbnail"].startswith("http"))


class ChangeMyPasswordViewTests(TestCase):
    def setUp(self):
        self.org = make_organization()
        self.user = make_user(self.org, groups=["operadores"])
        self.url = reverse("user-me-change-password")

    def test_cambia_la_contrasena_con_la_actual_correcta(self):
        response = authenticated_client(self.user).post(
            self.url, {"current_password": "Contrasena-123", "new_password": "OtraContrasena-999"},
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OtraContrasena-999"))
        self.assertFalse(self.user.must_change_password)

    def test_falla_si_la_actual_es_incorrecta(self):
        response = authenticated_client(self.user).post(
            self.url, {"current_password": "incorrecta", "new_password": "OtraContrasena-999"},
        )
        self.assertEqual(response.status_code, 400)

    def test_apaga_must_change_password_despues_de_un_reset_de_admin(self):
        self.user.must_change_password = True
        self.user.save(update_fields=["must_change_password"])
        authenticated_client(self.user).post(
            self.url, {"current_password": "Contrasena-123", "new_password": "OtraContrasena-999"},
        )
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)


class MeViewTests(TestCase):
    def test_devuelve_el_perfil_del_usuario_autenticado(self):
        org = make_organization()
        user = make_user(org, groups=["analistas_datos"])
        response = authenticated_client(user).get(reverse("user-me"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], user.email)
        self.assertEqual(response.data["organization_id"], org.id)
        self.assertEqual(response.data["groups"], ["analistas_datos"])

    def test_expone_los_permisos_efectivos_para_que_el_front_no_hardcodee_el_rol(self):
        org = make_organization()
        user = make_user(org, groups=["administradores"])
        response = authenticated_client(user).get(reverse("user-me"))
        self.assertIn("users.add_user", response.data["permissions"])
        self.assertIn("menu.change_menuopcion", response.data["permissions"])


class LoginViewTests(TestCase):
    def test_login_devuelve_access_y_refresh_con_claims_multi_tenant(self):
        import jwt as pyjwt

        org = make_organization()
        user = make_user(org, groups=["administradores"], email="admin@org-prueba.test")
        response = self.client.post(
            reverse("auth-login"), {"email": user.email, "password": "Contrasena-123"},
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        claims = pyjwt.decode(response.data["access"], options={"verify_signature": False})
        self.assertEqual(claims["org_id"], org.id)
        self.assertEqual(claims["grupos"], ["administradores"])
        self.assertEqual(claims["email"], user.email)

    def test_login_con_contrasena_incorrecta_falla(self):
        org = make_organization()
        user = make_user(org)
        response = self.client.post(reverse("auth-login"), {"email": user.email, "password": "incorrecta"})
        self.assertEqual(response.status_code, 401)
