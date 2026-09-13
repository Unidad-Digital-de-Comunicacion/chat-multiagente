from django.test import TestCase
from django.urls import reverse

from common.test_utils import authenticated_client, make_organization, make_user
from teams.models import Team

from .defaults import ETIQUETAS_SISTEMA
from .models import Etiqueta


class EtiquetaViewSetTests(TestCase):
    def setUp(self):
        self.org_a = make_organization(name="Org A", slug="org-a")
        self.org_b = make_organization(name="Org B", slug="org-b")
        self.admin_a = make_user(self.org_a, groups=["administradores"])
        self.admin_b = make_user(self.org_b, groups=["administradores"])
        self.operador_a = make_user(self.org_a, groups=["operadores"])
        self.team_a = Team.objects.create(organization=self.org_a, name="Ventas")
        self.list_url = reverse("etiqueta-list")

    def test_las_7_etiquetas_de_sistema_se_autogeneran_al_listar(self):
        response = authenticated_client(self.admin_a).get(self.list_url)
        self.assertEqual(response.status_code, 200)
        codigos = {e["codigo"] for e in response.data["results"] if e["es_sistema"]}
        self.assertEqual(codigos, {d["codigo"] for d in ETIQUETAS_SISTEMA})
        self.assertEqual(Etiqueta.objects.filter(organization=self.org_a, es_sistema=True).count(), 7)

    def test_las_etiquetas_de_sistema_no_se_duplican_si_se_lista_dos_veces(self):
        authenticated_client(self.admin_a).get(self.list_url)
        authenticated_client(self.admin_a).get(self.list_url)
        self.assertEqual(Etiqueta.objects.filter(organization=self.org_a, es_sistema=True).count(), 7)

    def test_cada_organizacion_tiene_su_propia_copia_de_las_etiquetas_de_sistema(self):
        authenticated_client(self.admin_a).get(self.list_url)
        authenticated_client(self.admin_b).get(self.list_url)
        pendiente_a = Etiqueta.objects.get(organization=self.org_a, codigo="pendiente")
        pendiente_b = Etiqueta.objects.get(organization=self.org_b, codigo="pendiente")
        self.assertNotEqual(pendiente_a.id, pendiente_b.id)

    def test_operador_no_puede_leer_ni_crear_etiquetas(self):
        # Core es sólo la API de autenticación de un operador — no tiene ningún permiso sobre
        # el catálogo de etiquetas ni el resto de la configuración (`users.group_permissions`).
        self.assertEqual(authenticated_client(self.operador_a).get(self.list_url).status_code, 403)
        self.assertEqual(
            authenticated_client(self.operador_a).post(
                self.list_url, {"nombre": "Urgente", "color": "#FF0000"},
            ).status_code,
            403,
        )

    def test_admin_crea_etiqueta_general(self):
        response = authenticated_client(self.admin_a).post(
            self.list_url, {"nombre": "Urgente", "color": "#ff0000"},
        )
        self.assertEqual(response.status_code, 201, response.data)
        etiqueta = Etiqueta.objects.get(pk=response.data["id"])
        self.assertEqual(etiqueta.organization_id, self.org_a.id)
        self.assertIsNone(etiqueta.team_id)
        self.assertFalse(etiqueta.es_sistema)
        self.assertEqual(etiqueta.color, "#FF0000")

    def test_el_campo_team_se_ignora_al_crear_una_etiqueta_a_mano(self):
        # "cada equipo es una etiqueta" es 100% automático — nunca se elige
        # un equipo a mano al crear una etiqueta general.
        response = authenticated_client(self.admin_a).post(
            self.list_url, {"nombre": "Urgente", "color": "#ff0000", "team": self.team_a.id},
        )
        self.assertEqual(response.status_code, 201, response.data)
        etiqueta = Etiqueta.objects.get(pk=response.data["id"])
        self.assertIsNone(etiqueta.team_id)

    def test_color_invalido_es_rechazado(self):
        response = authenticated_client(self.admin_a).post(
            self.list_url, {"nombre": "Urgente", "color": "rojo"},
        )
        self.assertEqual(response.status_code, 400)

    def test_color_de_texto_invalido_es_rechazado(self):
        response = authenticated_client(self.admin_a).post(
            self.list_url, {"nombre": "Urgente", "color": "#FF0000", "color_texto": "gris"},
        )
        self.assertEqual(response.status_code, 400)

    def test_admin_elige_el_color_de_la_fuente_al_crear_una_etiqueta(self):
        response = authenticated_client(self.admin_a).post(
            self.list_url, {"nombre": "Urgente", "color": "#FFEE00", "color_texto": "#000000"},
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["color_texto"], "#000000")

    def test_admin_puede_recolorear_una_etiqueta_de_sistema(self):
        authenticated_client(self.admin_a).get(self.list_url)  # autogenera las 7
        pendiente = Etiqueta.objects.get(organization=self.org_a, codigo="pendiente")
        url = reverse("etiqueta-detail", args=[pendiente.id])
        response = authenticated_client(self.admin_a).patch(url, {"color": "#000000", "color_texto": "#FFFFFF"})
        self.assertEqual(response.status_code, 200, response.data)
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.color, "#000000")
        self.assertEqual(pendiente.color_texto, "#FFFFFF")

    def test_no_puede_renombrar_una_etiqueta_de_sistema(self):
        authenticated_client(self.admin_a).get(self.list_url)
        pendiente = Etiqueta.objects.get(organization=self.org_a, codigo="pendiente")
        url = reverse("etiqueta-detail", args=[pendiente.id])
        response = authenticated_client(self.admin_a).patch(url, {"nombre": "Otra cosa"})
        self.assertEqual(response.status_code, 400)
        pendiente.refresh_from_db()
        self.assertEqual(pendiente.nombre, "Pendiente")

    def test_no_puede_borrar_una_etiqueta_de_sistema(self):
        authenticated_client(self.admin_a).get(self.list_url)
        pendiente = Etiqueta.objects.get(organization=self.org_a, codigo="pendiente")
        url = reverse("etiqueta-detail", args=[pendiente.id])
        response = authenticated_client(self.admin_a).delete(url)
        self.assertEqual(response.status_code, 400)
        self.assertTrue(Etiqueta.objects.filter(pk=pendiente.id).exists())

    def test_admin_puede_borrar_una_etiqueta_general_custom(self):
        etiqueta = Etiqueta.objects.create(organization=self.org_a, nombre="Urgente", color="#FF0000")
        url = reverse("etiqueta-detail", args=[etiqueta.id])
        response = authenticated_client(self.admin_a).delete(url)
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Etiqueta.objects.filter(pk=etiqueta.id).exists())

    def test_lista_solo_etiquetas_de_la_propia_organizacion(self):
        authenticated_client(self.admin_b).get(self.list_url)
        response = authenticated_client(self.admin_a).get(self.list_url)
        orgs = {Etiqueta.objects.get(pk=e["id"]).organization_id for e in response.data["results"]}
        self.assertEqual(orgs, {self.org_a.id})

    def test_admin_no_puede_editar_etiqueta_de_otra_organizacion_por_id(self):
        etiqueta_b = Etiqueta.objects.create(organization=self.org_b, nombre="Urgente", color="#FF0000")
        url = reverse("etiqueta-detail", args=[etiqueta_b.id])
        response = authenticated_client(self.admin_a).patch(url, {"color": "#000000"})
        self.assertEqual(response.status_code, 404)
        etiqueta_b.refresh_from_db()
        self.assertEqual(etiqueta_b.color, "#FF0000")

    def test_filtra_por_equipo(self):
        Etiqueta.objects.create(organization=self.org_a, nombre="General", color="#111111")
        response = authenticated_client(self.admin_a).get(self.list_url, {"team": self.team_a.id})
        nombres = {e["nombre"] for e in response.data["results"]}
        self.assertEqual(nombres, {"Ventas"})  # la autogenerada para team_a


class EtiquetaDeEquipoTests(TestCase):
    """"Cada equipo es una etiqueta": una etiqueta autogenerada por Team,
    sincronizada con su nombre, protegida como las de sistema."""

    def setUp(self):
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        self.team = Team.objects.create(organization=self.org, name="Soporte")
        self.list_url = reverse("etiqueta-list")

    def test_se_autogenera_una_etiqueta_por_cada_equipo_al_listar(self):
        response = authenticated_client(self.admin).get(self.list_url)
        self.assertEqual(response.status_code, 200)
        etiqueta = Etiqueta.objects.get(organization=self.org, team=self.team)
        self.assertEqual(etiqueta.nombre, "Soporte")
        self.assertFalse(etiqueta.es_sistema)

    def test_no_se_duplica_si_se_lista_dos_veces(self):
        authenticated_client(self.admin).get(self.list_url)
        authenticated_client(self.admin).get(self.list_url)
        self.assertEqual(Etiqueta.objects.filter(organization=self.org, team=self.team).count(), 1)

    def test_se_crea_para_un_equipo_nuevo_aunque_ya_existiera_el_catalogo(self):
        authenticated_client(self.admin).get(self.list_url)
        nuevo_equipo = Team.objects.create(organization=self.org, name="Postventa")
        authenticated_client(self.admin).get(self.list_url)
        self.assertTrue(Etiqueta.objects.filter(organization=self.org, team=nuevo_equipo).exists())

    def test_renombrar_el_equipo_renombra_su_etiqueta(self):
        authenticated_client(self.admin).get(self.list_url)
        self.team.name = "Soporte Técnico"
        self.team.save()
        authenticated_client(self.admin).get(self.list_url)
        etiqueta = Etiqueta.objects.get(organization=self.org, team=self.team)
        self.assertEqual(etiqueta.nombre, "Soporte Técnico")

    def test_no_se_puede_renombrar_la_etiqueta_de_equipo_a_mano(self):
        authenticated_client(self.admin).get(self.list_url)
        etiqueta = Etiqueta.objects.get(organization=self.org, team=self.team)
        url = reverse("etiqueta-detail", args=[etiqueta.id])
        response = authenticated_client(self.admin).patch(url, {"nombre": "Otro nombre"})
        self.assertEqual(response.status_code, 400)

    def test_se_puede_recolorear_la_etiqueta_de_equipo(self):
        authenticated_client(self.admin).get(self.list_url)
        etiqueta = Etiqueta.objects.get(organization=self.org, team=self.team)
        url = reverse("etiqueta-detail", args=[etiqueta.id])
        response = authenticated_client(self.admin).patch(url, {"color": "#00FF00"})
        self.assertEqual(response.status_code, 200, response.data)

    def test_no_se_puede_borrar_la_etiqueta_de_equipo_a_mano(self):
        authenticated_client(self.admin).get(self.list_url)
        etiqueta = Etiqueta.objects.get(organization=self.org, team=self.team)
        url = reverse("etiqueta-detail", args=[etiqueta.id])
        response = authenticated_client(self.admin).delete(url)
        self.assertEqual(response.status_code, 400)

    def test_borrar_el_equipo_borra_su_etiqueta(self):
        authenticated_client(self.admin).get(self.list_url)
        self.assertTrue(Etiqueta.objects.filter(organization=self.org, team=self.team).exists())
        team_id = self.team.id
        self.team.delete()  # Model.delete() deja el pk en None en la instancia, por eso lo guardamos antes.
        self.assertFalse(Etiqueta.objects.filter(organization=self.org, team_id=team_id).exists())
