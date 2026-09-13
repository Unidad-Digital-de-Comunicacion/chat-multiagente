from django.test import TestCase
from django.urls import reverse

from common.test_utils import authenticated_client, make_organization, make_user

from . import defaults
from .models import BotMessages


class BotMessagesModelTests(TestCase):
    def test_valor_o_default_devuelve_el_default_si_esta_vacio(self):
        org = make_organization()
        mensajes = BotMessages.objects.create(organization=org)
        self.assertEqual(mensajes.valor_o_default("mensaje_bienvenida"), defaults.MENSAJE_BIENVENIDA)

    def test_valor_o_default_devuelve_lo_cargado_si_no_esta_vacio(self):
        org = make_organization()
        mensajes = BotMessages.objects.create(organization=org, mensaje_bienvenida="Hola personalizado")
        self.assertEqual(mensajes.valor_o_default("mensaje_bienvenida"), "Hola personalizado")


class BotMessagesViewTests(TestCase):
    def setUp(self):
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        self.operador = make_user(self.org, groups=["operadores"])
        self.otra_org = make_organization(name="Otra", slug="otra")
        self.url = reverse("bot-messages")

    def test_se_crea_solo_en_el_primer_get(self):
        self.assertFalse(BotMessages.objects.filter(organization=self.org).exists())
        response = authenticated_client(self.admin).get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(BotMessages.objects.filter(organization=self.org).exists())

    def test_get_incluye_valores_efectivos_con_los_defaults(self):
        response = authenticated_client(self.admin).get(self.url)
        self.assertEqual(response.data["valores_efectivos"]["mensaje_despedida"], defaults.MENSAJE_DESPEDIDA)

    def test_admin_puede_editar(self):
        response = authenticated_client(self.admin).patch(self.url, {"mensaje_bienvenida": "Bienvenido a UCD"})
        self.assertEqual(response.status_code, 200, response.data)
        self.org.refresh_from_db()
        self.assertEqual(self.org.mensajes_bot.mensaje_bienvenida, "Bienvenido a UCD")

    def test_operador_no_puede_editar(self):
        response = authenticated_client(self.operador).patch(self.url, {"mensaje_bienvenida": "Hackeado"})
        self.assertEqual(response.status_code, 403)

    def test_operador_no_puede_ver(self):
        # `operadores` no tiene `bot_settings.view_botmessages` (grupo de
        # sólo lectura de equipos/horario por ahora) — StrictDjangoModelPermissions
        # bloquea el GET.
        response = authenticated_client(self.operador).get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_cada_organizacion_tiene_sus_propios_mensajes(self):
        admin_otra = make_user(self.otra_org, groups=["administradores"])
        authenticated_client(self.admin).patch(self.url, {"mensaje_bienvenida": "Hola de mi org"})
        response = authenticated_client(admin_otra).get(self.url)
        self.assertNotEqual(response.data["mensaje_bienvenida"], "Hola de mi org")
