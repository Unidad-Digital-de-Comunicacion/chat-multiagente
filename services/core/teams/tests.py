from django.test import TestCase
from django.urls import reverse

from common.test_utils import authenticated_client, make_organization, make_user

from .models import Team


class TeamViewSetTests(TestCase):
    def setUp(self):
        self.org_a = make_organization(name="Org A", slug="org-a")
        self.org_b = make_organization(name="Org B", slug="org-b")
        self.admin_a = make_user(self.org_a, groups=["administradores"])
        self.operador_a = make_user(self.org_a, groups=["operadores"])
        self.team_a = Team.objects.create(organization=self.org_a, name="Ventas")
        self.team_b = Team.objects.create(organization=self.org_b, name="Ventas")
        self.list_url = reverse("team-list")

    def test_lista_solo_equipos_de_la_propia_organizacion(self):
        response = authenticated_client(self.admin_a).get(self.list_url)
        nombres_ids = {t["id"] for t in response.data["results"]}
        self.assertIn(self.team_a.id, nombres_ids)
        self.assertNotIn(self.team_b.id, nombres_ids)

    def test_operador_puede_leer_pero_no_crear_equipos(self):
        # Necesita ver el nombre de los equipos para derivar una conversación
        # (`conversations.views.ConversacionViewSet.derivar`), pero no puede
        # administrarlos — eso sigue siendo sólo de `administradores`
        # (`users.group_permissions`).
        self.assertEqual(authenticated_client(self.operador_a).get(self.list_url).status_code, 200)
        self.assertEqual(
            authenticated_client(self.operador_a).post(self.list_url, {"name": "Soporte"}).status_code, 403,
        )

    def test_admin_crea_equipo_en_su_organizacion(self):
        response = authenticated_client(self.admin_a).post(self.list_url, {"name": "Soporte"})
        self.assertEqual(response.status_code, 201, response.data)
        equipo = Team.objects.get(pk=response.data["id"])
        self.assertEqual(equipo.organization_id, self.org_a.id)

    def test_no_puede_agregar_miembro_de_otra_organizacion(self):
        miembro_ajeno = make_user(self.org_b, groups=["operadores"])
        url = reverse("team-detail", args=[self.team_a.id])
        response = authenticated_client(self.admin_a).patch(url, {"members": [miembro_ajeno.id]})
        self.assertEqual(response.status_code, 400)

    def test_admin_no_puede_ver_ni_editar_un_equipo_de_otra_organizacion_por_id(self):
        # Mismo permiso Django (`teams.view_team`/`change_team`) en ambos
        # admins — el bloqueo tiene que venir del scoping por organización.
        url = reverse("team-detail", args=[self.team_b.id])
        self.assertEqual(authenticated_client(self.admin_a).get(url).status_code, 404)
        response = authenticated_client(self.admin_a).patch(url, {"name": "Hackeado"})
        self.assertEqual(response.status_code, 404)
        self.team_b.refresh_from_db()
        self.assertEqual(self.team_b.name, "Ventas")

    def test_admin_no_puede_borrar_un_equipo_de_otra_organizacion_por_id(self):
        url = reverse("team-detail", args=[self.team_b.id])
        response = authenticated_client(self.admin_a).delete(url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Team.objects.filter(pk=self.team_b.id).exists())

    def test_superusuario_de_plataforma_no_puede_gestionar_equipos(self):
        # `OrganizationScopedModelViewSet` es exclusivamente de recursos de UNA organización — ni
        # siquiera un `is_superuser=True` real hace excepción a propósito (antes sí la hacía): el
        # superusuario de plataforma gestiona organizaciones/usuarios/tokens desde la sección
        # "Plataforma", nunca equipos/menú/mensajes/etiquetas/horarios/canales de una organización
        # puntual — ver `common.viewsets.OrganizationScopedModelViewSet`.
        superusuario = make_user(
            None, groups=["superusuarios"], email="superusuario@plataforma.test",
            is_staff=True, is_superuser=True,
        )
        self.assertEqual(authenticated_client(superusuario).get(self.list_url).status_code, 403)
        self.assertEqual(
            authenticated_client(superusuario).post(self.list_url, {"name": "Soporte"}).status_code, 403,
        )
