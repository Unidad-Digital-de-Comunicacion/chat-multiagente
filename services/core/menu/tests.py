from django.test import TestCase
from django.urls import reverse

from common.test_utils import authenticated_client, make_organization, make_user
from teams.models import Team
from users.models import User

from .models import MenuOpcion


class MenuOpcionSlugTests(TestCase):
    def test_slug_se_autogenera_del_texto(self):
        org = make_organization()
        opcion = MenuOpcion.objects.create(organization=org, texto="Horarios de atención", tipo=MenuOpcion.Tipo.SUBMENU)
        self.assertEqual(opcion.slug, "horarios-de-atencion")

    def test_dos_organizaciones_pueden_reusar_el_mismo_slug(self):
        org_a = make_organization(name="Org A", slug="org-a")
        org_b = make_organization(name="Org B", slug="org-b")
        opcion_a = MenuOpcion.objects.create(organization=org_a, texto="Soporte", tipo=MenuOpcion.Tipo.SUBMENU)
        opcion_b = MenuOpcion.objects.create(organization=org_b, texto="Soporte", tipo=MenuOpcion.Tipo.SUBMENU)
        self.assertEqual(opcion_a.slug, opcion_b.slug)

    def test_slug_duplicado_en_la_misma_organizacion_se_desambigua(self):
        org = make_organization()
        opcion_1 = MenuOpcion.objects.create(organization=org, texto="Soporte", tipo=MenuOpcion.Tipo.SUBMENU)
        opcion_2 = MenuOpcion.objects.create(organization=org, texto="Soporte", tipo=MenuOpcion.Tipo.SUBMENU)
        self.assertNotEqual(opcion_1.slug, opcion_2.slug)


class MenuOpcionViewSetTests(TestCase):
    def setUp(self):
        self.org = make_organization()
        self.admin = make_user(self.org, role=User.Role.ADMIN)
        self.operador = make_user(self.org, role=User.Role.OPERADOR)
        self.otra_org = make_organization(name="Otra", slug="otra")
        self.team = Team.objects.create(organization=self.org, name="Ventas")
        self.list_url = reverse("menu-opcion-list")

    def test_derivacion_sin_equipo_falla(self):
        payload = {"texto": "Hablar con un operador", "tipo": MenuOpcion.Tipo.DERIVACION}
        response = authenticated_client(self.admin).post(self.list_url, payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("team", response.data)

    def test_derivacion_con_equipo_de_otra_organizacion_falla(self):
        team_ajeno = Team.objects.create(organization=self.otra_org, name="Ventas")
        payload = {"texto": "Hablar con un operador", "tipo": MenuOpcion.Tipo.DERIVACION, "team": team_ajeno.id}
        response = authenticated_client(self.admin).post(self.list_url, payload)
        self.assertEqual(response.status_code, 400)

    def test_derivacion_valida_se_crea(self):
        payload = {"texto": "Hablar con un operador", "tipo": MenuOpcion.Tipo.DERIVACION, "team": self.team.id}
        response = authenticated_client(self.admin).post(self.list_url, payload)
        self.assertEqual(response.status_code, 201, response.data)

    def test_respuesta_sin_texto_falla(self):
        payload = {"texto": "Horario de atención", "tipo": MenuOpcion.Tipo.RESPUESTA}
        response = authenticated_client(self.admin).post(self.list_url, payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("respuesta_texto", response.data)

    def test_operador_no_puede_crear_opciones(self):
        payload = {"texto": "Menú", "tipo": MenuOpcion.Tipo.SUBMENU}
        response = authenticated_client(self.operador).post(self.list_url, payload)
        self.assertEqual(response.status_code, 403)

    def test_no_ve_opciones_de_otra_organizacion(self):
        MenuOpcion.objects.create(organization=self.otra_org, texto="Secreto", tipo=MenuOpcion.Tipo.SUBMENU)
        response = authenticated_client(self.admin).get(self.list_url)
        textos = {o["texto"] for o in response.data["results"]}
        self.assertNotIn("Secreto", textos)

    def test_endpoint_tree_anida_por_parent(self):
        raiz = MenuOpcion.objects.create(organization=self.org, texto="Menú principal", tipo=MenuOpcion.Tipo.SUBMENU)
        MenuOpcion.objects.create(
            organization=self.org, texto="Sub", tipo=MenuOpcion.Tipo.RESPUESTA,
            respuesta_texto="ok", parent=raiz,
        )
        response = authenticated_client(self.admin).get(reverse("menu-opcion-tree"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["texto"], "Menú principal")
        self.assertEqual(len(response.data[0]["hijos"]), 1)
