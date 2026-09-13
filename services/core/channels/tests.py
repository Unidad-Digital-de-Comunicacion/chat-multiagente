from unittest.mock import Mock, patch

import requests
from django.test import TestCase
from django.urls import reverse

from common.test_utils import authenticated_client, make_organization, make_user

from .models import Canal


class CanalViewSetTests(TestCase):
    def setUp(self):
        self.org_a = make_organization(name="Org A", slug="org-a")
        self.org_b = make_organization(name="Org B", slug="org-b")
        self.admin_a = make_user(self.org_a, groups=["administradores"])
        self.operador_a = make_user(self.org_a, groups=["operadores"])
        self.list_url = reverse("canal-list")

    def test_los_4_canales_se_autogeneran_al_listar(self):
        response = authenticated_client(self.admin_a).get(self.list_url)
        self.assertEqual(response.status_code, 200)
        tipos = {c["tipo"] for c in response.data["results"]}
        self.assertEqual(tipos, {"WHATSAPP", "MESSENGER", "INSTAGRAM", "WEBCHAT"})
        self.assertEqual(Canal.objects.filter(organization=self.org_a).count(), 4)

    def test_no_se_duplican_si_se_lista_dos_veces(self):
        authenticated_client(self.admin_a).get(self.list_url)
        authenticated_client(self.admin_a).get(self.list_url)
        self.assertEqual(Canal.objects.filter(organization=self.org_a).count(), 4)

    def test_vienen_desactivados_y_sin_api_key_por_default(self):
        authenticated_client(self.admin_a).get(self.list_url)
        canal = Canal.objects.get(organization=self.org_a, tipo="WHATSAPP")
        self.assertFalse(canal.activo)
        self.assertEqual(canal.api_key, "")

    def test_operador_no_puede_ver_los_canales(self):
        response = authenticated_client(self.operador_a).get(self.list_url)
        self.assertEqual(response.status_code, 403)

    def test_superusuario_de_plataforma_no_configura_api_keys_externas(self):
        # El superusuario de plataforma ve el ESTADO de las apis externas (sólo lectura, agregado
        # de todas las organizaciones — `platform_admin.views.ExternalApiHealthView`) pero no
        # configura la api key de ningún canal externo puntual, eso sigue siendo de cada Admin de
        # organización — ver `common.viewsets.OrganizationScopedModelViewSet`.
        superusuario = make_user(
            None, groups=["superusuarios"], email="superusuario@plataforma.test",
            is_staff=True, is_superuser=True,
        )
        self.assertEqual(authenticated_client(superusuario).get(self.list_url).status_code, 403)

    def test_api_key_nunca_se_devuelve_por_la_api(self):
        authenticated_client(self.admin_a).get(self.list_url)
        canal = Canal.objects.get(organization=self.org_a, tipo="WHATSAPP")
        url = reverse("canal-detail", args=[canal.id])
        response = authenticated_client(self.admin_a).patch(url, {"api_key": "secreta-1234"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn("api_key", response.data)
        self.assertEqual(response.data["api_key_preview"], "••••1234")
        self.assertTrue(response.data["api_key_configurada"])
        canal.refresh_from_db()
        self.assertEqual(canal.api_key, "secreta-1234")

    def test_admin_puede_activar_un_canal(self):
        authenticated_client(self.admin_a).get(self.list_url)
        canal = Canal.objects.get(organization=self.org_a, tipo="WHATSAPP")
        url = reverse("canal-detail", args=[canal.id])
        response = authenticated_client(self.admin_a).patch(url, {"activo": True})
        self.assertEqual(response.status_code, 200, response.data)
        canal.refresh_from_db()
        self.assertTrue(canal.activo)

    def test_no_se_pueden_crear_canales_por_api(self):
        # Ningún grupo tiene `channels.add_canal` a propósito — los 4
        # canales son fijos, no se crean a mano — así que
        # `StrictDjangoModelPermissions` lo bloquea con 403.
        response = authenticated_client(self.admin_a).post(self.list_url, {"tipo": "WHATSAPP"})
        self.assertEqual(response.status_code, 403)

    def test_no_se_pueden_borrar_canales_por_api(self):
        authenticated_client(self.admin_a).get(self.list_url)
        canal = Canal.objects.get(organization=self.org_a, tipo="WHATSAPP")
        url = reverse("canal-detail", args=[canal.id])
        response = authenticated_client(self.admin_a).delete(url)
        self.assertEqual(response.status_code, 403)

    def test_lista_solo_canales_de_la_propia_organizacion(self):
        authenticated_client(self.admin_a).get(self.list_url)
        admin_b = make_user(self.org_b, groups=["administradores"])
        authenticated_client(admin_b).get(self.list_url)
        response = authenticated_client(self.admin_a).get(self.list_url)
        orgs = {Canal.objects.get(pk=c["id"]).organization_id for c in response.data["results"]}
        self.assertEqual(orgs, {self.org_a.id})

    def test_admin_no_puede_editar_canal_de_otra_organizacion_por_id(self):
        authenticated_client(self.admin_a).get(self.list_url)
        admin_b = make_user(self.org_b, groups=["administradores"])
        authenticated_client(admin_b).get(self.list_url)
        canal_b = Canal.objects.get(organization=self.org_b, tipo="WHATSAPP")
        url = reverse("canal-detail", args=[canal_b.id])
        response = authenticated_client(self.admin_a).patch(url, {"activo": True})
        self.assertEqual(response.status_code, 404)


class CanalVerificarConexionTests(TestCase):
    """`POST /canales/{id}/verificar/` — chequeo real contra el servidor
    remoto (mockeado acá: la suite nunca debe pegarle de verdad a la Graph
    API de Meta)."""

    def setUp(self):
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        self.operador = make_user(self.org, groups=["operadores"])
        authenticated_client(self.admin).get(reverse("canal-list"))  # autogenera los 4
        self.whatsapp = Canal.objects.get(organization=self.org, tipo="WHATSAPP")
        self.webchat = Canal.objects.get(organization=self.org, tipo="WEBCHAT")

    def _verificar(self, user, canal):
        return authenticated_client(user).post(reverse("canal-verificar", args=[canal.id]))

    def test_sin_api_key_cargada_no_intenta_conectar(self):
        with patch("channels.health.requests.get") as mock_get:
            response = self._verificar(self.admin, self.whatsapp)
        mock_get.assert_not_called()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["ultimo_chequeo_ok"])
        self.assertIn("api key", response.data["ultimo_chequeo_detalle"])

    def test_webchat_no_intenta_conectar_a_ningun_servidor(self):
        self.webchat.api_key = "lo-que-sea"
        self.webchat.save(update_fields=["api_key"])
        with patch("channels.health.requests.get") as mock_get:
            response = self._verificar(self.admin, self.webchat)
        mock_get.assert_not_called()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data["ultimo_chequeo_ok"])

    def test_chequeo_exitoso_contra_la_graph_api(self):
        self.whatsapp.api_key = "token-valido"
        self.whatsapp.save(update_fields=["api_key"])
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {"id": "123456", "name": "Mi Empresa"}
        with patch("channels.health.requests.get", return_value=mock_response) as mock_get:
            response = self._verificar(self.admin, self.whatsapp)
        mock_get.assert_called_once()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["ultimo_chequeo_ok"])
        self.assertIn("Mi Empresa", response.data["ultimo_chequeo_detalle"])
        self.assertIsNotNone(response.data["ultimo_chequeo_at"])

    def test_chequeo_fallido_por_token_invalido(self):
        self.whatsapp.api_key = "token-vencido"
        self.whatsapp.save(update_fields=["api_key"])
        mock_response = Mock(status_code=400)
        mock_response.json.return_value = {"error": {"message": "Invalid OAuth access token"}}
        with patch("channels.health.requests.get", return_value=mock_response):
            response = self._verificar(self.admin, self.whatsapp)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["ultimo_chequeo_ok"])
        self.assertEqual(response.data["ultimo_chequeo_detalle"], "Invalid OAuth access token")

    def test_chequeo_no_se_pudo_conectar(self):
        self.whatsapp.api_key = "token"
        self.whatsapp.save(update_fields=["api_key"])
        with patch("channels.health.requests.get", side_effect=requests.ConnectionError("timeout")):
            response = self._verificar(self.admin, self.whatsapp)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(response.data["ultimo_chequeo_ok"])
        self.assertIn("No se pudo conectar", response.data["ultimo_chequeo_detalle"])

    def test_operador_no_puede_verificar(self):
        response = self._verificar(self.operador, self.whatsapp)
        self.assertEqual(response.status_code, 403)

    def test_resultado_del_chequeo_queda_guardado_en_la_base(self):
        self.whatsapp.api_key = "token-valido"
        self.whatsapp.save(update_fields=["api_key"])
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {"id": "1", "name": "OK"}
        with patch("channels.health.requests.get", return_value=mock_response):
            self._verificar(self.admin, self.whatsapp)
        self.whatsapp.refresh_from_db()
        self.assertTrue(self.whatsapp.ultimo_chequeo_ok)
        self.assertIsNotNone(self.whatsapp.ultimo_chequeo_at)
