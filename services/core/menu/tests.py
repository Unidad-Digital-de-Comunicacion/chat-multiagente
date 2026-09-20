from django.test import TestCase
from django.urls import reverse

from common.test_utils import authenticated_client, make_organization, make_user
from teams.models import Team

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
        self.admin = make_user(self.org, groups=["administradores"])
        self.operador = make_user(self.org, groups=["operadores"])
        self.otra_org = make_organization(name="Otra", slug="otra")
        self.team = Team.objects.create(organization=self.org, name="Ventas")
        self.list_url = reverse("menu-opcion-list")

    def test_derivacion_sin_equipo_falla(self):
        payload = {"texto": "Hablar con un operador", "tipo": MenuOpcion.Tipo.DERIVACION}
        response = authenticated_client(self.admin).post(self.list_url, payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("team", response.data["error"]["detail"])

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
        self.assertIn("respuesta_texto", response.data["error"]["detail"])

    def test_operador_no_puede_crear_opciones(self):
        payload = {"texto": "Menú", "tipo": MenuOpcion.Tipo.SUBMENU}
        response = authenticated_client(self.operador).post(self.list_url, payload)
        self.assertEqual(response.status_code, 403)

    def test_no_ve_opciones_de_otra_organizacion(self):
        MenuOpcion.objects.create(organization=self.otra_org, texto="Secreto", tipo=MenuOpcion.Tipo.SUBMENU)
        response = authenticated_client(self.admin).get(self.list_url)
        textos = {o["texto"] for o in response.data["results"]}
        self.assertNotIn("Secreto", textos)

    def test_admin_no_puede_ver_ni_editar_una_opcion_de_otra_organizacion_por_id(self):
        # Mismo permiso Django (`menu.view_menuopcion`/`change_menuopcion`)
        # en cualquier admin — el bloqueo lo tiene que dar el scoping por
        # organización del queryset, no el permiso, que es global.
        ajena = MenuOpcion.objects.create(organization=self.otra_org, texto="Secreto", tipo=MenuOpcion.Tipo.TERMINAR)
        url = reverse("menu-opcion-detail", args=[ajena.id])
        self.assertEqual(authenticated_client(self.admin).get(url).status_code, 404)
        response = authenticated_client(self.admin).patch(url, {"texto": "Hackeado"})
        self.assertEqual(response.status_code, 404)
        ajena.refresh_from_db()
        self.assertEqual(ajena.texto, "Secreto")

    def test_admin_no_puede_borrar_una_opcion_de_otra_organizacion_por_id(self):
        ajena = MenuOpcion.objects.create(organization=self.otra_org, texto="Secreto", tipo=MenuOpcion.Tipo.TERMINAR)
        url = reverse("menu-opcion-detail", args=[ajena.id])
        response = authenticated_client(self.admin).delete(url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(MenuOpcion.objects.filter(pk=ajena.id).exists())

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


class MenuOpcionReordenarTests(TestCase):
    """Reordenar/reparentar por drag-and-drop — mismo contrato que
    chatbot/static/js/chatbot_menu.js::guardarOrden (portado)."""

    def setUp(self):
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        self.operador = make_user(self.org, groups=["operadores"])
        self.otra_org = make_organization(name="Otra", slug="otra")
        self.url = reverse("menu-opcion-reordenar")

    def test_reordena_hermanos_en_la_raiz(self):
        a = MenuOpcion.objects.create(organization=self.org, texto="A", tipo=MenuOpcion.Tipo.TERMINAR, orden=0)
        b = MenuOpcion.objects.create(organization=self.org, texto="B", tipo=MenuOpcion.Tipo.TERMINAR, orden=1)
        response = authenticated_client(self.admin).post(
            self.url, {"parent_id": None, "orden": [b.id, a.id]}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual((b.orden, a.orden), (0, 1))

    def test_orden_que_no_es_una_lista_falla(self):
        response = authenticated_client(self.admin).post(
            self.url, {"parent_id": None, "orden": "no-es-una-lista"}, format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_orden_vacio_falla(self):
        response = authenticated_client(self.admin).post(self.url, {"parent_id": None, "orden": []}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_reparenta_dentro_de_un_submenu(self):
        raiz = MenuOpcion.objects.create(organization=self.org, texto="Menú", tipo=MenuOpcion.Tipo.SUBMENU)
        suelto = MenuOpcion.objects.create(organization=self.org, texto="Suelto", tipo=MenuOpcion.Tipo.TERMINAR)
        response = authenticated_client(self.admin).post(
            self.url, {"parent_id": raiz.id, "orden": [suelto.id]}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        suelto.refresh_from_db()
        self.assertEqual(suelto.parent_id, raiz.id)

    def test_no_permite_reparentar_dentro_de_si_mismo(self):
        raiz = MenuOpcion.objects.create(organization=self.org, texto="Menú", tipo=MenuOpcion.Tipo.SUBMENU)
        hijo = MenuOpcion.objects.create(
            organization=self.org, texto="Hijo", tipo=MenuOpcion.Tipo.SUBMENU, parent=raiz,
        )
        response = authenticated_client(self.admin).post(
            self.url, {"parent_id": hijo.id, "orden": [raiz.id]}, format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_padre_debe_ser_tipo_submenu(self):
        respuesta = MenuOpcion.objects.create(
            organization=self.org, texto="R", tipo=MenuOpcion.Tipo.RESPUESTA, respuesta_texto="ok",
        )
        suelto = MenuOpcion.objects.create(organization=self.org, texto="Suelto", tipo=MenuOpcion.Tipo.TERMINAR)
        response = authenticated_client(self.admin).post(
            self.url, {"parent_id": respuesta.id, "orden": [suelto.id]}, format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_no_puede_mover_un_nodo_de_otra_organizacion(self):
        ajeno = MenuOpcion.objects.create(organization=self.otra_org, texto="Ajeno", tipo=MenuOpcion.Tipo.TERMINAR)
        response = authenticated_client(self.admin).post(
            self.url, {"parent_id": None, "orden": [ajeno.id]}, format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_operador_no_puede_reordenar(self):
        nodo = MenuOpcion.objects.create(organization=self.org, texto="A", tipo=MenuOpcion.Tipo.TERMINAR)
        response = authenticated_client(self.operador).post(
            self.url, {"parent_id": None, "orden": [nodo.id]}, format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_superusuario_de_plataforma_no_puede_reordenar(self):
        superusuario = make_user(
            None, groups=["superusuarios"], email="superusuario@plataforma.test",
            is_staff=True, is_superuser=True,
        )
        nodo = MenuOpcion.objects.create(organization=self.org, texto="A", tipo=MenuOpcion.Tipo.TERMINAR)
        response = authenticated_client(superusuario).post(
            self.url, {"parent_id": None, "orden": [nodo.id]}, format="json",
        )
        self.assertEqual(response.status_code, 403)
