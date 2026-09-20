import tempfile
from pathlib import Path

from django.test import TestCase
from django.urls import reverse

from channels.models import Canal
from common.test_utils import authenticated_client, make_organization, make_service_token, make_user
from conversations.models import Contact, Conversacion
from teams.models import Team

from rest_framework.test import APIClient

from .models import MetaAppConfig, ServiceToken
from .views import DOCUMENTOS_TECNICOS


def _make_superusuario(email="superusuario@plataforma.test"):
    return make_user(None, groups=["superusuarios"], email=email, is_staff=True, is_superuser=True)


class ServiceTokenViewSetTests(TestCase):
    def setUp(self):
        self.superusuario = _make_superusuario()
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        self.list_url = reverse("plataforma-token-servicio-list")

    def test_los_5_servicios_se_autogeneran_al_listar(self):
        response = authenticated_client(self.superusuario).get(self.list_url)
        self.assertEqual(response.status_code, 200, response.data)
        servicios = {t["servicio"] for t in response.data["results"]}
        self.assertEqual(servicios, {s for s, _ in ServiceToken.Servicio.choices})
        self.assertEqual(ServiceToken.objects.count(), 5)

    def test_no_se_duplican_si_se_lista_dos_veces(self):
        authenticated_client(self.superusuario).get(self.list_url)
        authenticated_client(self.superusuario).get(self.list_url)
        self.assertEqual(ServiceToken.objects.count(), 5)

    def test_admin_de_organizacion_no_puede_entrar(self):
        response = authenticated_client(self.admin).get(self.list_url)
        self.assertEqual(response.status_code, 403)

    def test_el_token_nunca_se_devuelve_por_la_api(self):
        authenticated_client(self.superusuario).get(self.list_url)
        token = ServiceToken.objects.first()
        url = reverse("plataforma-token-servicio-detail", args=[token.id])
        authenticated_client(self.superusuario).patch(url, {"token": "secreto-de-verdad"})
        response = authenticated_client(self.superusuario).get(url)
        self.assertNotIn("secreto-de-verdad", str(response.data))
        self.assertTrue(response.data["token_configurado"])
        self.assertEqual(response.data["token_preview"], "••••rdad")

    def test_generar_devuelve_el_token_en_texto_plano_una_vez(self):
        authenticated_client(self.superusuario).get(self.list_url)
        token = ServiceToken.objects.first()
        url = reverse("plataforma-token-servicio-generar", args=[token.id])
        response = authenticated_client(self.superusuario).post(url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("token", response.data)
        token.refresh_from_db()
        self.assertEqual(token.token, response.data["token"])
        self.assertIsNotNone(token.generado_at)

    def test_admin_no_puede_generar(self):
        authenticated_client(self.superusuario).get(self.list_url)
        token = ServiceToken.objects.first()
        url = reverse("plataforma-token-servicio-generar", args=[token.id])
        response = authenticated_client(self.admin).post(url)
        self.assertEqual(response.status_code, 403)

    def test_no_tiene_alta_ni_baja(self):
        authenticated_client(self.superusuario).get(self.list_url)
        token = ServiceToken.objects.first()
        url = reverse("plataforma-token-servicio-detail", args=[token.id])
        self.assertEqual(authenticated_client(self.superusuario).post(self.list_url).status_code, 405)
        self.assertEqual(authenticated_client(self.superusuario).delete(url).status_code, 405)


class MetaAppConfigViewTests(TestCase):
    """`GET/PATCH /api/core/plataforma/meta-app/` — singleton editable sólo
    por el superusuario de plataforma (ver `platform_admin.models.
    MetaAppConfig`)."""

    def setUp(self):
        self.superusuario = _make_superusuario()
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        self.url = reverse("plataforma-meta-app")

    def test_get_devuelve_la_fila_unica(self):
        # `MetaAppConfig.obtener()` ya la creó (la migración de datos la
        # siembra desde META_APP_ID/META_APP_SECRET la primera vez) — acá
        # sólo se confirma que sigue siendo una sola fila y que el shape es
        # el esperado, no un valor puntual (depende del entorno).
        response = authenticated_client(self.superusuario).get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("app_id", response.data)
        self.assertIn("app_secret_configurada", response.data)
        self.assertEqual(MetaAppConfig.objects.count(), 1)

    def test_admin_de_organizacion_no_puede_entrar(self):
        response = authenticated_client(self.admin).get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_patch_carga_app_id_y_app_secret(self):
        response = authenticated_client(self.superusuario).patch(
            self.url, {"app_id": "1123752986744511", "app_secret": "el-secreto-real"},
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["app_id"], "1123752986744511")
        self.assertTrue(response.data["app_secret_configurada"])
        self.assertEqual(response.data["app_secret_preview"], "••••real")
        self.assertEqual(response.data["app_secret_valor"], "el-secreto-real")
        config = MetaAppConfig.obtener()
        self.assertEqual(config.app_id, "1123752986744511")
        self.assertEqual(config.app_secret, "el-secreto-real")

    def test_patch_parcial_no_borra_el_otro_campo(self):
        MetaAppConfig.objects.update_or_create(pk=1, defaults={"app_id": "viejo-id", "app_secret": "viejo-secreto"})
        response = authenticated_client(self.superusuario).patch(self.url, {"app_id": "nuevo-id"})
        self.assertEqual(response.status_code, 200, response.data)
        config = MetaAppConfig.obtener()
        self.assertEqual(config.app_id, "nuevo-id")
        self.assertEqual(config.app_secret, "viejo-secreto")

    def test_admin_no_puede_editar(self):
        MetaAppConfig.objects.update_or_create(pk=1, defaults={"app_id": "viejo-id"})
        response = authenticated_client(self.admin).patch(self.url, {"app_id": "x"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(MetaAppConfig.obtener().app_id, "viejo-id")


class InternalMetaAppConfigViewTests(TestCase):
    """`GET /api/core/internal/meta-app/` — el único lugar donde `app_secret`
    sale de Core en texto plano, y sólo para Channel Gateway autenticado con
    su `ServiceToken` (mismo criterio que `InternalCanalConfigView`)."""

    def setUp(self):
        MetaAppConfig.objects.update_or_create(pk=1, defaults={"app_id": "1123752986744511", "app_secret": "s3cr3t"})
        self.url = reverse("internal-meta-app")
        make_service_token(ServiceToken.Servicio.CHANNEL_GATEWAY, "token-de-gateway", activo=True)

    def _get(self, token=None):
        client = APIClient()
        if token is not None:
            client.credentials(HTTP_AUTHORIZATION=f"Service-Token {token}")
        return client.get(self.url)

    def test_channel_gateway_puede_leer_la_config_con_su_token(self):
        response = self._get(token="token-de-gateway")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["app_id"], "1123752986744511")
        self.assertEqual(response.data["app_secret"], "s3cr3t")

    def test_token_invalido_es_rechazado(self):
        response = self._get(token="no-es-el-token-correcto")
        self.assertEqual(response.status_code, 401)

    def test_jwt_de_superusuario_no_alcanza(self):
        # Autenticado como usuario real pero sin `ServiceToken` en `request.
        # auth` -> falla el permiso, no la autenticación (403, no 401) —
        # mismo criterio que `InternalCanalConfigViewTests`.
        superusuario = _make_superusuario()
        response = authenticated_client(superusuario).get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_token_de_otro_servicio_no_alcanza(self):
        make_service_token(ServiceToken.Servicio.CONVERSATION_ENGINE, "token-de-otro-servicio", activo=True)
        response = self._get(token="token-de-otro-servicio")
        self.assertEqual(response.status_code, 403)


class PlatformStatsViewTests(TestCase):
    def setUp(self):
        self.superusuario = _make_superusuario()
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        make_user(self.org, groups=["operadores"])
        Team.objects.create(organization=self.org, name="Ventas")
        self.url = reverse("plataforma-estadisticas")

    def test_superusuario_ve_las_estadisticas(self):
        response = authenticated_client(self.superusuario).get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["organizaciones_total"], 1)
        self.assertEqual(response.data["usuarios_total"], 3)  # admin + operador + superusuario
        self.assertEqual(response.data["equipos_total"], 1)
        desglose = response.data["por_organizacion"]
        self.assertEqual(len(desglose), 1)
        self.assertEqual(desglose[0]["usuarios"], 2)  # sólo los de la organización, no el superusuario

    def test_admin_no_puede_entrar(self):
        response = authenticated_client(self.admin).get(self.url)
        self.assertEqual(response.status_code, 403)


class ExternalApiHealthViewTests(TestCase):
    def setUp(self):
        self.superusuario = _make_superusuario()
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        authenticated_client(self.admin).get(reverse("canal-list"))  # autogenera los 4 canales
        self.url = reverse("plataforma-salud-canales")

    def test_superusuario_ve_la_salud_de_todos_los_canales(self):
        response = authenticated_client(self.superusuario).get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data), 4)
        tipos = {c["tipo"] for c in response.data}
        self.assertEqual(tipos, {t for t, _ in Canal.Tipo.choices})

    def test_admin_no_puede_entrar(self):
        response = authenticated_client(self.admin).get(self.url)
        self.assertEqual(response.status_code, 403)


class HistorialConversacionesPlatformViewTests(TestCase):
    """`GET /plataforma/historial-conversaciones/` — mismo shape resumido
    que `conversations.views.ConversacionViewSet.historial`, pero de TODAS
    las organizaciones a la vez y sólo para el superusuario real."""

    def setUp(self):
        self.superusuario = _make_superusuario()
        self.org_a = make_organization(name="Org A", slug="org-a")
        self.org_b = make_organization(name="Org B", slug="org-b")
        self.admin = make_user(self.org_a, groups=["administradores"])
        self.url = reverse("plataforma-historial-conversaciones")

        contact_a = Contact.objects.create(organization=self.org_a, canal="WHATSAPP", identificador_externo="111")
        contact_b = Contact.objects.create(organization=self.org_b, canal="WHATSAPP", identificador_externo="222")
        Conversacion.objects.create(organization=self.org_a, contact=contact_a, canal="WHATSAPP")
        Conversacion.objects.create(organization=self.org_b, contact=contact_b, canal="WHATSAPP")

    def test_superusuario_ve_las_conversaciones_de_todas_las_organizaciones(self):
        response = authenticated_client(self.superusuario).get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 2)
        organizaciones = {fila["organization_id"] for fila in response.data["results"]}
        self.assertEqual(organizaciones, {self.org_a.id, self.org_b.id})

    def test_ordenado_por_organizacion(self):
        response = authenticated_client(self.superusuario).get(self.url)
        nombres = [fila["organization_nombre"] for fila in response.data["results"]]
        self.assertEqual(nombres, sorted(nombres))

    def test_admin_no_puede_entrar(self):
        response = authenticated_client(self.admin).get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_no_incluye_mensajes(self):
        response = authenticated_client(self.superusuario).get(self.url)
        self.assertNotIn("mensajes", response.data["results"][0])


class ManualDownloadViewTests(TestCase):
    def setUp(self):
        self.superusuario = _make_superusuario()
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        self.url = reverse("plataforma-manual")

    def test_superusuario_puede_descargar_el_manual(self):
        response = authenticated_client(self.superusuario).get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_admin_no_puede_descargarlo(self):
        response = authenticated_client(self.admin).get(self.url)
        self.assertEqual(response.status_code, 403)


class DocumentoTecnicoViewTests(TestCase):
    """`DOCUMENTOS_TECNICOS` apunta a paths montados por docker-compose.yml
    (ver sus comentarios) — acá se sustituye el path de un slug por un
    archivo temporal para no depender de que ese mount exista en el
    ambiente donde corren los tests."""

    def setUp(self):
        self.superusuario = _make_superusuario()
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])

    def test_superusuario_puede_descargar_un_documento_existente(self):
        with tempfile.NamedTemporaryFile(suffix=".md") as archivo:
            archivo.write(b"# Contrato de prueba")
            archivo.flush()
            original = DOCUMENTOS_TECNICOS["operators-desk-api"]["path"]
            DOCUMENTOS_TECNICOS["operators-desk-api"]["path"] = Path(archivo.name)
            try:
                url = reverse("plataforma-manual-documento", args=["operators-desk-api"])
                response = authenticated_client(self.superusuario).get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response["Content-Type"].startswith("text/markdown"))
            finally:
                DOCUMENTOS_TECNICOS["operators-desk-api"]["path"] = original

    def test_slug_desconocido_da_404(self):
        url = reverse("plataforma-manual-documento", args=["no-existe"])
        response = authenticated_client(self.superusuario).get(url)
        self.assertEqual(response.status_code, 404)

    def test_documento_sin_montar_todavia_da_404(self):
        # Mismo caso que un ambiente donde todavía no se agregó el mount
        # de docker-compose.yml para ese path (`docs_repo`/`agents_android.md`).
        original = DOCUMENTOS_TECNICOS["operators-desk-api"]["path"]
        DOCUMENTOS_TECNICOS["operators-desk-api"]["path"] = Path("/no/existe/nada/aca.md")
        try:
            url = reverse("plataforma-manual-documento", args=["operators-desk-api"])
            response = authenticated_client(self.superusuario).get(url)
            self.assertEqual(response.status_code, 404)
        finally:
            DOCUMENTOS_TECNICOS["operators-desk-api"]["path"] = original

    def test_admin_no_puede_descargar_documentos_tecnicos(self):
        url = reverse("plataforma-manual-documento", args=["operators-desk-api"])
        response = authenticated_client(self.admin).get(url)
        self.assertEqual(response.status_code, 403)


class PlatformSchemaViewTests(TestCase):
    """El esquema OpenAPI es público a propósito (`AllowAny`) — Swagger UI/
    Redoc lo piden con un `fetch()` propio del navegador sin el header
    `Authorization` (no tienen forma de conocer el JWT, que vive en el
    `localStorage` de otro origen); si exigiera auth, ese primer fetch
    fallaría con 401 y el visor nunca llegaría a levantar, antes de poder
    ofrecer ningún botón "Authorize" para pegar el token. Sólo expone la
    FORMA de la API (paths/params/campos), nunca datos reales — esos
    siguen exigiendo autenticación real en cada endpoint de verdad. Lo que
    sí sigue acotado al superusuario es el link en el menú (`Layout.tsx`)."""

    def setUp(self):
        self.superusuario = _make_superusuario()
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        self.url = reverse("plataforma-schema")

    def test_superusuario_puede_ver_el_esquema(self):
        response = authenticated_client(self.superusuario).get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_admin_tambien_puede_verlo(self):
        response = authenticated_client(self.admin).get(self.url)
        self.assertEqual(response.status_code, 200)

    def test_un_anonimo_tambien_puede_verlo_es_a_proposito(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
