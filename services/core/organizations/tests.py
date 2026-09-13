from django.test import TestCase
from django.urls import reverse

from common.test_utils import authenticated_client, make_organization, make_user
from users.models import User

from .models import Organization


class MyOrganizationViewTests(TestCase):
    def setUp(self):
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        self.operador = make_user(self.org, groups=["operadores"])
        self.otra_org = make_organization(name="Otra org", slug="otra-org")
        self.url = reverse("organization-me")

    def test_devuelve_la_organizacion_del_usuario_autenticado(self):
        response = authenticated_client(self.admin).get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.org.id)

    def test_admin_puede_editar_su_organizacion(self):
        response = authenticated_client(self.admin).patch(self.url, {"name": "Nuevo nombre"})
        self.assertEqual(response.status_code, 200)
        self.org.refresh_from_db()
        self.assertEqual(self.org.name, "Nuevo nombre")

    def test_operador_no_puede_ver_ni_editar_la_organizacion(self):
        # `operadores` no tiene ningún permiso sobre Core más allá de su propio perfil y la
        # recuperación de usuario/contraseña — Core es sólo su API de autenticación, el resto
        # de las pantallas son de administradores/superusuarios (`users.group_permissions`).
        self.assertEqual(authenticated_client(self.operador).get(self.url).status_code, 403)
        self.assertEqual(
            authenticated_client(self.operador).patch(self.url, {"name": "Otro nombre"}).status_code, 403,
        )

    def test_superusuario_de_plataforma_no_puede_usar_este_endpoint(self):
        # `organizations.view_organization`/`change_organization` son los mismos permisos que
        # tiene el grupo "superusuarios" para esto — pero el objeto que resuelve
        # `MyOrganizationView.get_object` es "mi propia organización", y una cuenta de plataforma
        # no tiene una (antes esto era un 500: `Organization.objects.get(pk=None)`). El
        # superusuario gestiona TODAS las organizaciones desde
        # `/api/core/plataforma/organizaciones/`, no desde acá.
        superusuario = make_user(
            None, groups=["superusuarios"], email="superusuario@plataforma.test",
            is_staff=True, is_superuser=True,
        )
        self.assertEqual(authenticated_client(superusuario).get(self.url).status_code, 403)

    def test_nunca_devuelve_datos_de_otra_organizacion(self):
        response = authenticated_client(self.admin).get(self.url)
        self.assertNotEqual(response.data["id"], self.otra_org.id)


class PlatformOrganizationViewSetTests(TestCase):
    """Sección "Plataforma" del Admin Panel: administración de TODAS las
    organizaciones, sólo para el superusuario real (`IsPlatformSuperuser`)
    — ni un Admin de organización (mismos permisos Django que el
    superusuario para `organizations.*`, pero acotado a la suya propia) ni
    un miembro del grupo "superusuarios" sin `is_superuser=True` real
    pueden entrar acá, sólo mirar/editar la propia vía `organization-me`."""

    def setUp(self):
        self.org_a = make_organization(name="Org A", slug="org-a")
        self.org_b = make_organization(name="Org B", slug="org-b")
        self.superusuario = make_user(
            None, groups=["superusuarios"], email="superusuario@plataforma.test",
            is_staff=True, is_superuser=True,
        )
        self.admin_a = make_user(self.org_a, groups=["administradores"])
        # Miembro del grupo "superusuarios" pero SIN el flag real de Django —
        # per diseño, no alcanza para entrar a las vistas de alcance global.
        self.superusuario_sin_flag = make_user(
            None, groups=["superusuarios"], email="staff-sin-flag@plataforma.test", is_staff=True,
        )
        self.list_url = reverse("plataforma-organizacion-list")

    def test_superusuario_ve_todas_las_organizaciones(self):
        response = authenticated_client(self.superusuario).get(self.list_url)
        self.assertEqual(response.status_code, 200, response.data)
        ids = {o["id"] for o in response.data["results"]}
        self.assertEqual(ids, {self.org_a.id, self.org_b.id})

    def test_admin_de_organizacion_no_puede_entrar(self):
        response = authenticated_client(self.admin_a).get(self.list_url)
        self.assertEqual(response.status_code, 403)

    def test_grupo_superusuarios_sin_is_superuser_real_no_puede_entrar(self):
        response = authenticated_client(self.superusuario_sin_flag).get(self.list_url)
        self.assertEqual(response.status_code, 403)

    def test_superusuario_puede_crear_una_organizacion(self):
        payload = {"name": "Org Nueva", "slug": "org-nueva", "plan": "profesional"}
        response = authenticated_client(self.superusuario).post(self.list_url, payload)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(self.org_a.__class__.objects.filter(slug="org-nueva").exists())

    def test_superusuario_puede_editar_limites_y_plan(self):
        url = reverse("plataforma-organizacion-detail", args=[self.org_a.id])
        response = authenticated_client(self.superusuario).patch(url, {
            "connection_limit": 10, "user_limit": 50, "monthly_conversation_limit": 5000,
            "plan": "enterprise", "is_active": False,
        })
        self.assertEqual(response.status_code, 200, response.data)
        self.org_a.refresh_from_db()
        self.assertEqual(self.org_a.connection_limit, 10)
        self.assertEqual(self.org_a.user_limit, 50)
        self.assertEqual(self.org_a.monthly_conversation_limit, 5000)
        self.assertEqual(self.org_a.plan, "enterprise")
        self.assertFalse(self.org_a.is_active)

    def test_los_limites_son_0_por_default_es_decir_ilimitado(self):
        self.assertEqual(self.org_a.connection_limit, 0)
        self.assertEqual(self.org_a.user_limit, 0)
        self.assertEqual(self.org_a.monthly_conversation_limit, 0)

    def test_eliminar_es_un_soft_delete(self):
        url = reverse("plataforma-organizacion-detail", args=[self.org_a.id])
        response = authenticated_client(self.superusuario).delete(url)
        self.assertEqual(response.status_code, 204)
        self.org_a.refresh_from_db()
        self.assertIsNotNone(self.org_a.deleted_at)
        self.assertFalse(self.org_a.is_active)
        self.assertTrue(Organization.objects.filter(pk=self.org_a.id).exists())  # nunca se borra

    def test_una_organizacion_eliminada_no_aparece_en_el_listado_por_default(self):
        authenticated_client(self.superusuario).delete(reverse("plataforma-organizacion-detail", args=[self.org_a.id]))
        response = authenticated_client(self.superusuario).get(self.list_url)
        ids = {o["id"] for o in response.data["results"]}
        self.assertNotIn(self.org_a.id, ids)

    def test_incluir_eliminadas_las_trae_de_vuelta(self):
        authenticated_client(self.superusuario).delete(reverse("plataforma-organizacion-detail", args=[self.org_a.id]))
        response = authenticated_client(self.superusuario).get(self.list_url, {"incluir_eliminadas": "1"})
        ids = {o["id"] for o in response.data["results"]}
        self.assertIn(self.org_a.id, ids)

    def test_eliminar_una_organizacion_elimina_tambien_a_sus_usuarios(self):
        usuario = make_user(self.org_a, groups=["administradores"], email="otro-admin@org-a.test")
        authenticated_client(self.superusuario).delete(reverse("plataforma-organizacion-detail", args=[self.org_a.id]))
        for u in (self.admin_a, usuario):
            u.refresh_from_db()
            self.assertIsNotNone(u.deleted_at)
            self.assertFalse(u.is_active)

    def test_restaurar_reactiva_la_organizacion_y_los_usuarios_eliminados_con_ella(self):
        # Un usuario que YA estaba eliminado de antes (a mano, no como parte de este soft delete
        # de la organización) no se reactiva solo porque se restauró la organización.
        ya_eliminado = make_user(self.org_a, groups=["administradores"], email="ya-eliminado@org-a.test")
        authenticated_client(self.superusuario).delete(reverse("plataforma-usuario-detail", args=[ya_eliminado.id]))
        authenticated_client(self.superusuario).delete(reverse("plataforma-organizacion-detail", args=[self.org_a.id]))

        response = authenticated_client(self.superusuario).post(
            reverse("plataforma-organizacion-restaurar", args=[self.org_a.id]),
        )
        self.assertEqual(response.status_code, 200, response.data)

        self.org_a.refresh_from_db()
        self.admin_a.refresh_from_db()
        ya_eliminado.refresh_from_db()
        self.assertIsNone(self.org_a.deleted_at)
        self.assertTrue(self.org_a.is_active)
        self.assertIsNone(self.admin_a.deleted_at)
        self.assertTrue(self.admin_a.is_active)
        self.assertIsNotNone(ya_eliminado.deleted_at)  # sigue eliminado, no formaba parte de este soft delete

    def test_admin_no_puede_eliminar_organizaciones(self):
        url = reverse("plataforma-organizacion-detail", args=[self.org_a.id])
        response = authenticated_client(self.admin_a).delete(url)
        self.assertEqual(response.status_code, 403)
