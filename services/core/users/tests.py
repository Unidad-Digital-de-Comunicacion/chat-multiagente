from django.test import TestCase
from django.urls import reverse

from common.test_utils import authenticated_client, make_organization, make_user
from users.models import User


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
        self.admin_a = make_user(self.org_a, role=User.Role.ADMIN)
        self.operador_a = make_user(self.org_a, role=User.Role.OPERADOR)
        self.admin_b = make_user(self.org_b, role=User.Role.ADMIN)
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

    def test_admin_crea_usuario_queda_en_su_propia_organizacion(self):
        payload = {"email": "nuevo@org-a.test", "password": "Contrasena-123", "role": User.Role.OPERADOR}
        response = authenticated_client(self.admin_a).post(self.list_url, payload)
        self.assertEqual(response.status_code, 201, response.data)
        nuevo = User.objects.get(email="nuevo@org-a.test")
        self.assertEqual(nuevo.organization_id, self.org_a.id)

    def test_admin_no_puede_forzar_organizacion_ajena_en_el_body(self):
        payload = {
            "email": "otro@org-a.test", "password": "Contrasena-123",
            "role": User.Role.OPERADOR, "organization": self.org_b.id,
        }
        response = authenticated_client(self.admin_a).post(self.list_url, payload)
        self.assertEqual(response.status_code, 201, response.data)
        nuevo = User.objects.get(email="otro@org-a.test")
        self.assertEqual(nuevo.organization_id, self.org_a.id)


class MeViewTests(TestCase):
    def test_devuelve_el_perfil_del_usuario_autenticado(self):
        org = make_organization()
        user = make_user(org, role=User.Role.DATA_MANAGER)
        response = authenticated_client(user).get(reverse("user-me"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], user.email)
        self.assertEqual(response.data["organization_id"], org.id)


class LoginViewTests(TestCase):
    def test_login_devuelve_access_y_refresh_con_claims_multi_tenant(self):
        import jwt as pyjwt

        org = make_organization()
        user = make_user(org, role=User.Role.ADMIN, email="admin@org-prueba.test")
        response = self.client.post(
            reverse("auth-login"), {"email": user.email, "password": "Contrasena-123"},
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        claims = pyjwt.decode(response.data["access"], options={"verify_signature": False})
        self.assertEqual(claims["org_id"], org.id)
        self.assertEqual(claims["rol"], User.Role.ADMIN)
        self.assertEqual(claims["email"], user.email)

    def test_login_con_contrasena_incorrecta_falla(self):
        org = make_organization()
        user = make_user(org)
        response = self.client.post(reverse("auth-login"), {"email": user.email, "password": "incorrecta"})
        self.assertEqual(response.status_code, 401)
