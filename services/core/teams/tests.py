from django.test import TestCase
from django.urls import reverse

from common.test_utils import authenticated_client, make_organization, make_user
from users.models import User

from .models import Team


class TeamViewSetTests(TestCase):
    def setUp(self):
        self.org_a = make_organization(name="Org A", slug="org-a")
        self.org_b = make_organization(name="Org B", slug="org-b")
        self.admin_a = make_user(self.org_a, role=User.Role.ADMIN)
        self.operador_a = make_user(self.org_a, role=User.Role.OPERADOR)
        self.team_a = Team.objects.create(organization=self.org_a, name="Ventas")
        self.team_b = Team.objects.create(organization=self.org_b, name="Ventas")
        self.list_url = reverse("team-list")

    def test_lista_solo_equipos_de_la_propia_organizacion(self):
        response = authenticated_client(self.operador_a).get(self.list_url)
        nombres_ids = {t["id"] for t in response.data["results"]}
        self.assertIn(self.team_a.id, nombres_ids)
        self.assertNotIn(self.team_b.id, nombres_ids)

    def test_operador_puede_leer_pero_no_crear_equipos(self):
        response = authenticated_client(self.operador_a).post(self.list_url, {"name": "Soporte"})
        self.assertEqual(response.status_code, 403)

    def test_admin_crea_equipo_en_su_organizacion(self):
        response = authenticated_client(self.admin_a).post(self.list_url, {"name": "Soporte"})
        self.assertEqual(response.status_code, 201, response.data)
        equipo = Team.objects.get(pk=response.data["id"])
        self.assertEqual(equipo.organization_id, self.org_a.id)

    def test_no_puede_agregar_miembro_de_otra_organizacion(self):
        miembro_ajeno = make_user(self.org_b, role=User.Role.OPERADOR)
        url = reverse("team-detail", args=[self.team_a.id])
        response = authenticated_client(self.admin_a).patch(url, {"members": [miembro_ajeno.id]})
        self.assertEqual(response.status_code, 400)
