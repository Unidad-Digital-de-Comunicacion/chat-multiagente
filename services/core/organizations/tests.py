from django.test import TestCase
from django.urls import reverse

from common.test_utils import authenticated_client, make_organization, make_user


class MyOrganizationViewTests(TestCase):
    def setUp(self):
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        self.operador = make_user(self.org, groups=["operadores"])
        self.otra_org = make_organization(name="Otra org", slug="otra-org")
        self.url = reverse("organization-me")

    def test_devuelve_la_organizacion_del_usuario_autenticado(self):
        response = authenticated_client(self.operador).get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.org.id)

    def test_admin_puede_editar_su_organizacion(self):
        response = authenticated_client(self.admin).patch(self.url, {"name": "Nuevo nombre"})
        self.assertEqual(response.status_code, 200)
        self.org.refresh_from_db()
        self.assertEqual(self.org.name, "Nuevo nombre")

    def test_operador_no_puede_editar_la_organizacion(self):
        response = authenticated_client(self.operador).patch(self.url, {"name": "Otro nombre"})
        self.assertEqual(response.status_code, 403)

    def test_nunca_devuelve_datos_de_otra_organizacion(self):
        response = authenticated_client(self.operador).get(self.url)
        self.assertNotEqual(response.data["id"], self.otra_org.id)
