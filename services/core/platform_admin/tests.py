import tempfile
from pathlib import Path

from django.test import TestCase
from django.urls import reverse

from channels.models import Canal
from common.test_utils import authenticated_client, make_organization, make_user
from conversations.models import Contact, Conversacion
from teams.models import Team

from .models import ServiceToken
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
