from unittest.mock import Mock, patch

import requests
from django.test import TestCase
from django.urls import reverse

from common.test_utils import authenticated_client, make_organization, make_service_token, make_user
from platform_admin.models import MetaAppConfig, ServiceToken
from rest_framework.test import APIClient

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

    def test_el_campo_write_only_api_key_nunca_vuelve_por_la_api(self):
        # El campo de ESCRITURA `api_key` nunca vuelve tal cual (write-only
        # de verdad) — `api_key_valor` es un campo de LECTURA aparte,
        # deliberado (ver el test de abajo), no lo mismo.
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

    def test_api_key_valor_devuelve_el_valor_completo_a_proposito(self):
        # Excepción deliberada, pedida a mano: a diferencia del resto del
        # patrón write-only/preview de arriba, esto SÍ expone la
        # credencial completa — el Admin Panel decide si la muestra.
        authenticated_client(self.admin_a).get(self.list_url)
        canal = Canal.objects.get(organization=self.org_a, tipo="WHATSAPP")
        url = reverse("canal-detail", args=[canal.id])
        response = authenticated_client(self.admin_a).patch(url, {"api_key": "secreta-1234"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["api_key_valor"], "secreta-1234")

    def test_api_key_valor_es_null_sin_api_key_cargada(self):
        authenticated_client(self.admin_a).get(self.list_url)
        canal = Canal.objects.get(organization=self.org_a, tipo="INSTAGRAM")
        url = reverse("canal-detail", args=[canal.id])
        response = authenticated_client(self.admin_a).get(url)
        self.assertIsNone(response.data["api_key_valor"])

    def test_api_key_larga_como_un_token_real_de_whatsapp_se_guarda_entera(self):
        # Reproduce un DataError real: un token de sistema de la Cloud API
        # de WhatsApp puede superar los 255 caracteres que alcanzaban para
        # un Page Access Token de Messenger — `api_key` es `TextField` desde
        # que esto se detectó en vivo, no `CharField(max_length=255)`.
        authenticated_client(self.admin_a).get(self.list_url)
        canal = Canal.objects.get(organization=self.org_a, tipo="WHATSAPP")
        url = reverse("canal-detail", args=[canal.id])
        token_largo = "EAA" + "x" * 300
        response = authenticated_client(self.admin_a).patch(url, {"api_key": token_largo})
        self.assertEqual(response.status_code, 200, response.data)
        canal.refresh_from_db()
        self.assertEqual(canal.api_key, token_largo)

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
    API de Meta). Casos comunes a cualquier tipo de canal; WhatsApp y
    Messenger/Instagram tienen nodo/autenticación DISTINTOS del lado de
    Meta (ver `channels.health`), así que sus casos puntuales están en
    `CanalVerificarWhatsappTests`/`CanalVerificarMessengerTests` más abajo."""

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

    def test_operador_no_puede_verificar(self):
        response = self._verificar(self.operador, self.whatsapp)
        self.assertEqual(response.status_code, 403)


class CanalVerificarWhatsappTests(TestCase):
    """WhatsApp (Cloud API): el nodo real a consultar es el propio
    `phone_number_id` (`Canal.telefono_id`), NUNCA `/me` — un token de
    System User acotado al número no puede resolver `/me` aunque mande
    mensajes de verdad sin problema (`/me` es el bug real que reportó un
    canal andando en producción marcado como "sin conexión" acá). La
    autenticación va por header `Authorization: Bearer`, igual que el envío
    real (`channel-gateway/app/meta_client.py`), no por query param."""

    def setUp(self):
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        authenticated_client(self.admin).get(reverse("canal-list"))
        self.whatsapp = Canal.objects.get(organization=self.org, tipo="WHATSAPP")
        self.whatsapp.api_key = "token-de-system-user"
        self.whatsapp.telefono_id = "1234567890"
        self.whatsapp.save(update_fields=["api_key", "telefono_id"])

    def _verificar(self):
        return authenticated_client(self.admin).post(reverse("canal-verificar", args=[self.whatsapp.id]))

    def test_sin_telefono_id_no_intenta_conectar(self):
        self.whatsapp.telefono_id = ""
        self.whatsapp.save(update_fields=["telefono_id"])
        with patch("channels.health.requests.get") as mock_get:
            response = self._verificar()
        mock_get.assert_not_called()
        self.assertFalse(response.data["ultimo_chequeo_ok"])
        self.assertIn("Phone Number ID", response.data["ultimo_chequeo_detalle"])

    def test_consulta_el_nodo_del_telefono_no_me(self):
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {"id": "1234567890", "verified_name": "Mi Empresa"}
        with patch("channels.health.requests.get", return_value=mock_response) as mock_get:
            response = self._verificar()
        url_llamada = mock_get.call_args.args[0]
        self.assertTrue(url_llamada.endswith("/1234567890"))
        self.assertNotIn("/me", url_llamada)
        self.assertTrue(response.data["ultimo_chequeo_ok"])
        self.assertIn("Mi Empresa", response.data["ultimo_chequeo_detalle"])

    def test_autentica_por_header_bearer_no_por_query_param(self):
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {"id": "1234567890"}
        with patch("channels.health.requests.get", return_value=mock_response) as mock_get:
            self._verificar()
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer token-de-system-user")
        self.assertNotIn("access_token", kwargs.get("params", {}))

    def test_error_de_meta_incluye_el_code_en_el_detalle(self):
        mock_response = Mock(status_code=400)
        mock_response.json.return_value = {
            "error": {"message": "Unsupported get request.", "code": 100, "error_subcode": 33},
        }
        with patch("channels.health.requests.get", return_value=mock_response):
            response = self._verificar()
        self.assertFalse(response.data["ultimo_chequeo_ok"])
        self.assertIn("Unsupported get request.", response.data["ultimo_chequeo_detalle"])
        self.assertIn("code=100", response.data["ultimo_chequeo_detalle"])
        self.assertIn("subcode=33", response.data["ultimo_chequeo_detalle"])

    def test_no_se_pudo_conectar(self):
        with patch("channels.health.requests.get", side_effect=requests.ConnectionError("timeout")):
            response = self._verificar()
        self.assertFalse(response.data["ultimo_chequeo_ok"])
        self.assertIn("No se pudo conectar", response.data["ultimo_chequeo_detalle"])

    def test_resultado_queda_guardado_en_la_base(self):
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {"id": "1234567890"}
        with patch("channels.health.requests.get", return_value=mock_response):
            self._verificar()
        self.whatsapp.refresh_from_db()
        self.assertTrue(self.whatsapp.ultimo_chequeo_ok)
        self.assertIsNotNone(self.whatsapp.ultimo_chequeo_at)


class CanalVerificarMessengerTests(TestCase):
    """Messenger/Instagram: un token de página con sólo `pages_messaging`
    no puede leer `/me` (Meta exige `pages_read_engagement` — el error real
    que reportó un canal andando en producción marcado "sin conexión" acá).
    Se valida con `/debug_token` + credenciales de la APP en vez del token
    del canal, que es lo que la Graph API documenta para esto sin depender
    de qué permisos tenga el token puntual."""

    def setUp(self):
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        authenticated_client(self.admin).get(reverse("canal-list"))
        self.messenger = Canal.objects.get(organization=self.org, tipo="MESSENGER")
        self.messenger.api_key = "page-access-token"
        self.messenger.save(update_fields=["api_key"])
        MetaAppConfig.objects.update_or_create(pk=1, defaults={"app_id": "app-id", "app_secret": "app-secret"})

    def _verificar(self):
        return authenticated_client(self.admin).post(reverse("canal-verificar", args=[self.messenger.id]))

    def test_chequeo_exitoso_consulta_debug_token_con_credenciales_de_la_app(self):
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {"data": {"is_valid": True, "expires_at": 0}}
        with patch("channels.health.requests.get", return_value=mock_response) as mock_get:
            response = self._verificar()
        url_llamada = mock_get.call_args.args[0]
        _, kwargs = mock_get.call_args
        self.assertTrue(url_llamada.endswith("/debug_token"))
        self.assertEqual(kwargs["params"]["input_token"], "page-access-token")
        self.assertEqual(kwargs["params"]["access_token"], "app-id|app-secret")
        self.assertTrue(response.data["ultimo_chequeo_ok"])
        self.assertIn("no vence", response.data["ultimo_chequeo_detalle"])

    def test_token_con_permiso_de_solo_mensajeria_no_falla_mas_por_me(self):
        # Este es exactamente el caso que reportó un canal andando en
        # producción marcado "sin conexión": el token SÍ es válido para
        # mandar mensajes, `/me` no lo reconoce por falta de
        # `pages_read_engagement`. `/debug_token` no le pide ese permiso.
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {
            "data": {"is_valid": True, "scopes": ["pages_messaging"], "expires_at": 1798761600},
        }
        with patch("channels.health.requests.get", return_value=mock_response):
            response = self._verificar()
        self.assertTrue(response.data["ultimo_chequeo_ok"])

    def test_token_vencido_o_revocado(self):
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {
            "data": {"is_valid": False, "error": {"message": "Error validating access token: Session has expired."}},
        }
        with patch("channels.health.requests.get", return_value=mock_response):
            response = self._verificar()
        self.assertFalse(response.data["ultimo_chequeo_ok"])
        self.assertIn("Session has expired", response.data["ultimo_chequeo_detalle"])

    def test_sin_meta_app_id_o_secret_configurados_no_intenta_conectar(self):
        MetaAppConfig.objects.update_or_create(pk=1, defaults={"app_id": "", "app_secret": ""})
        with patch("channels.health.requests.get") as mock_get:
            response = self._verificar()
        mock_get.assert_not_called()
        self.assertFalse(response.data["ultimo_chequeo_ok"])
        self.assertIn("Plataforma", response.data["ultimo_chequeo_detalle"])

    def test_no_se_pudo_conectar(self):
        with patch("channels.health.requests.get", side_effect=requests.ConnectionError("timeout")):
            response = self._verificar()
        self.assertFalse(response.data["ultimo_chequeo_ok"])
        self.assertIn("No se pudo conectar", response.data["ultimo_chequeo_detalle"])


class CanalWebhookTests(TestCase):
    """`webhook_url`/`webhook_secret` (nuevos en `CanalSerializer`, para que
    Channel Gateway tenga con qué verificar un webhook entrante) y la action
    `regenerar-webhook-secret`."""

    def setUp(self):
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        self.operador = make_user(self.org, groups=["operadores"])
        authenticated_client(self.admin).get(reverse("canal-list"))  # autogenera los 4
        self.messenger = Canal.objects.get(organization=self.org, tipo="MESSENGER")
        self.webchat = Canal.objects.get(organization=self.org, tipo="WEBCHAT")

    def test_los_canales_meta_traen_webhook_url_y_secret(self):
        response = authenticated_client(self.admin).get(reverse("canal-detail", args=[self.messenger.id]))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["webhook_url"].endswith(f"/webhooks/messenger/{self.messenger.uuid}/"))
        self.assertEqual(response.data["webhook_secret"], self.messenger.webhook_secret)
        self.assertTrue(response.data["webhook_secret"])

    def test_webchat_no_tiene_webhook(self):
        response = authenticated_client(self.admin).get(reverse("canal-detail", args=[self.webchat.id]))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIsNone(response.data["webhook_url"])
        self.assertIsNone(response.data["webhook_secret"])

    def test_admin_puede_regenerar_el_secreto(self):
        anterior = self.messenger.webhook_secret
        url = reverse("canal-regenerar-webhook-secret", args=[self.messenger.id])
        response = authenticated_client(self.admin).post(url)
        self.assertEqual(response.status_code, 200, response.data)
        self.messenger.refresh_from_db()
        self.assertNotEqual(self.messenger.webhook_secret, anterior)
        self.assertEqual(response.data["webhook_secret"], self.messenger.webhook_secret)

    def test_operador_no_puede_regenerar(self):
        url = reverse("canal-regenerar-webhook-secret", args=[self.messenger.id])
        response = authenticated_client(self.operador).post(url)
        self.assertEqual(response.status_code, 403)

    def test_no_se_puede_regenerar_el_de_webchat(self):
        url = reverse("canal-regenerar-webhook-secret", args=[self.webchat.id])
        response = authenticated_client(self.admin).post(url)
        self.assertEqual(response.status_code, 400)


class InternalCanalConfigViewTests(TestCase):
    """`GET /api/core/internal/canales/<uuid>/` — el único lugar donde
    `api_key` sale de Core en texto plano, y sólo para Channel Gateway
    autenticado con su `ServiceToken` (`platform_admin.service_auth`)."""

    def setUp(self):
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        authenticated_client(self.admin).get(reverse("canal-list"))  # autogenera los 4
        self.messenger = Canal.objects.get(organization=self.org, tipo="MESSENGER")
        self.messenger.api_key = "page-access-token-secreto"
        self.messenger.save(update_fields=["api_key"])
        self.url = reverse("internal-canal-config", args=[self.messenger.uuid])
        self.token = make_service_token(ServiceToken.Servicio.CHANNEL_GATEWAY, "token-de-gateway", activo=True)

    def _get(self, token=None, header_scheme="Service-Token"):
        client = APIClient()
        if token is not None:
            client.credentials(HTTP_AUTHORIZATION=f"{header_scheme} {token}")
        return client.get(self.url)

    def test_channel_gateway_puede_leer_la_config_con_su_token(self):
        response = self._get(token="token-de-gateway")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["api_key"], "page-access-token-secreto")
        self.assertEqual(response.data["webhook_secret"], self.messenger.webhook_secret)
        self.assertEqual(response.data["organization_id"], self.org.id)
        self.assertEqual(response.data["tipo"], "MESSENGER")

    def test_token_invalido_es_rechazado(self):
        response = self._get(token="no-es-el-token-correcto")
        self.assertEqual(response.status_code, 401)

    def test_token_inactivo_es_rechazado(self):
        self.token.activo = False
        self.token.save(update_fields=["activo"])
        response = self._get(token="token-de-gateway")
        self.assertEqual(response.status_code, 401)

    def test_token_de_otro_servicio_no_alcanza(self):
        make_service_token(ServiceToken.Servicio.CONVERSATION_ENGINE, "token-de-otro-servicio", activo=True)
        response = self._get(token="token-de-otro-servicio")
        self.assertEqual(response.status_code, 403)

    def test_sin_autenticacion_no_se_puede_entrar(self):
        response = self._get(token=None)
        self.assertEqual(response.status_code, 401)

    def test_un_usuario_humano_con_jwt_no_puede_entrar(self):
        # Autenticado como usuario real (admin) pero sin `ServiceToken` en
        # `request.auth` -> falla el permiso, no la autenticación (403, no
        # 401) — mismo criterio que cualquier otro 403 de este proyecto.
        response = authenticated_client(self.admin).get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_uuid_inexistente_da_404(self):
        import uuid
        otro_url = reverse("internal-canal-config", args=[uuid.uuid4()])
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Service-Token token-de-gateway")
        response = client.get(otro_url)
        self.assertEqual(response.status_code, 404)


class InternalCanalPorOrganizacionViewTests(TestCase):
    """`GET /api/core/internal/canales/organizacion/<id>/<tipo>/` — Meta
    manda Messenger/Instagram/WhatsApp de una misma organización a la MISMA
    Callback URL (sólo deja configurar una por app), así que Channel
    Gateway necesita poder encontrar el canal "hermano" correcto de la
    misma organización cuando el `object` real del payload no coincide con
    el canal de la URL que Meta llamó."""

    def setUp(self):
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        authenticated_client(self.admin).get(reverse("canal-list"))  # autogenera los 4
        self.instagram = Canal.objects.get(organization=self.org, tipo="INSTAGRAM")
        self.instagram.api_key = "ig-token"
        self.instagram.save(update_fields=["api_key"])
        make_service_token(ServiceToken.Servicio.CHANNEL_GATEWAY, "token-de-gateway", activo=True)
        self.url = reverse("internal-canal-por-organizacion", args=[self.org.id, "instagram"])

    def _get(self, token="token-de-gateway"):
        client = APIClient()
        if token is not None:
            client.credentials(HTTP_AUTHORIZATION=f"Service-Token {token}")
        return client.get(self.url)

    def test_encuentra_el_canal_por_organizacion_y_tipo(self):
        response = self._get()
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["tipo"], "INSTAGRAM")
        self.assertEqual(response.data["api_key"], "ig-token")
        self.assertEqual(response.data["webhook_secret"], self.instagram.webhook_secret)

    def test_tipo_en_minuscula_tambien_funciona(self):
        # `self.url` ya se armó con "instagram" en minúscula en el setUp —
        # confirma que el `.upper()` de la vista lo normaliza bien.
        response = self._get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["tipo"], "INSTAGRAM")

    def test_organizacion_o_tipo_inexistente_da_404(self):
        url = reverse("internal-canal-por-organizacion", args=[999999, "instagram"])
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION="Service-Token token-de-gateway")
        self.assertEqual(client.get(url).status_code, 404)

    def test_requiere_service_token(self):
        response = self._get(token=None)
        self.assertEqual(response.status_code, 401)


class WhatsappExchangeTests(TestCase):
    """`POST /canales/{id}/whatsapp-exchange/` — el frontend le pasa el
    `code` que le dio el SDK de Facebook al terminar el Embedded Signup
    (más `phone_number_id`/`waba_id`, que vienen del mismo callback del
    SDK), y esto lo cambia por el `access_token` real contra Meta."""

    def setUp(self):
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        self.operador = make_user(self.org, groups=["operadores"])
        authenticated_client(self.admin).get(reverse("canal-list"))  # autogenera los 4
        self.whatsapp = Canal.objects.get(organization=self.org, tipo="WHATSAPP")
        self.messenger = Canal.objects.get(organization=self.org, tipo="MESSENGER")
        self.url = reverse("canal-whatsapp-exchange", args=[self.whatsapp.id])

    def test_intercambio_exitoso_guarda_todo(self):
        mock_response = Mock(status_code=200, content=b"1")
        mock_response.json.return_value = {"access_token": "el-token-real"}
        with patch("channels.embedded_signup.requests.get", return_value=mock_response) as mock_get:
            response = authenticated_client(self.admin).post(self.url, {
                "code": "el-code-del-popup", "phone_number_id": "111222333", "waba_id": "444555666",
            })
        self.assertEqual(response.status_code, 200, response.data)
        mock_get.assert_called_once()
        self.whatsapp.refresh_from_db()
        self.assertEqual(self.whatsapp.api_key, "el-token-real")
        self.assertEqual(self.whatsapp.telefono_id, "111222333")
        self.assertEqual(self.whatsapp.waba_id, "444555666")

    def test_falta_el_code(self):
        response = authenticated_client(self.admin).post(self.url, {"phone_number_id": "111"})
        self.assertEqual(response.status_code, 400)

    def test_no_aplica_a_otro_tipo_de_canal(self):
        url = reverse("canal-whatsapp-exchange", args=[self.messenger.id])
        response = authenticated_client(self.admin).post(url, {"code": "x"})
        self.assertEqual(response.status_code, 400)

    def test_error_de_meta_no_guarda_nada(self):
        mock_response = Mock(status_code=400, content=b"1")
        mock_response.json.return_value = {"error": {"message": "Invalid verification code format."}}
        with patch("channels.embedded_signup.requests.get", return_value=mock_response):
            response = authenticated_client(self.admin).post(self.url, {"code": "code-invalido"})
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("Invalid verification code format", str(response.data))
        self.whatsapp.refresh_from_db()
        self.assertEqual(self.whatsapp.api_key, "")

    def test_operador_no_puede_usarlo(self):
        response = authenticated_client(self.operador).post(self.url, {"code": "x"})
        self.assertEqual(response.status_code, 403)
