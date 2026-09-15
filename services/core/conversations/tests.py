from unittest.mock import patch

from bot_settings.models import BotMessages
from django.test import TestCase
from django.urls import reverse
from menu.models import MenuOpcion
from teams.models import Team

from common.test_utils import authenticated_client, make_organization, make_user
from platform_admin.models import ServiceToken
from rest_framework.test import APIClient

from .models import Contact, Conversacion, ConversacionLog


def _service_client(token):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Service-Token {token}")
    return client


class MensajeEntranteViewTests(TestCase):
    def setUp(self):
        self.org = make_organization()
        self.token = ServiceToken.objects.create(
            servicio=ServiceToken.Servicio.CHANNEL_GATEWAY, token="token-de-gateway", activo=True,
        )
        self.url = reverse("bot-mensaje-entrante")

    def _body(self, **overrides):
        body = {
            "organization_id": self.org.id, "channel": "WHATSAPP",
            "contact_externo_id": "5493511234567", "texto": "Hola, quería consultar",
        }
        body.update(overrides)
        return body

    def test_requiere_service_token(self):
        response = self.client.post(self.url, self._body(), content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_un_usuario_humano_no_puede_entrar(self):
        admin = make_user(self.org, groups=["administradores"])
        response = authenticated_client(admin).post(self.url, self._body())
        self.assertEqual(response.status_code, 403)

    def test_primer_mensaje_crea_contacto_y_conversacion_y_manda_bienvenida(self):
        response = _service_client("token-de-gateway").post(self.url, self._body(), format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["acciones"]), 1)
        self.assertEqual(response.data["acciones"][0]["tipo"], "enviar_texto")
        self.assertTrue(response.data["acciones"][0]["texto"])

        self.assertEqual(Contact.objects.count(), 1)
        contact = Contact.objects.get()
        self.assertEqual(contact.organization, self.org)
        self.assertEqual(contact.canal, "WHATSAPP")
        self.assertEqual(contact.identificador_externo, "5493511234567")

        self.assertEqual(Conversacion.objects.count(), 1)
        conversacion = Conversacion.objects.get()
        self.assertEqual(conversacion.estado, Conversacion.Estado.ABIERTA)
        self.assertIsNone(conversacion.operador)

        self.assertEqual(ConversacionLog.objects.count(), 1)
        log = ConversacionLog.objects.get()
        self.assertEqual(log.remitente, ConversacionLog.Remitente.CONTACTO)
        self.assertEqual(log.texto, "Hola, quería consultar")

    def test_segundo_mensaje_del_mismo_contacto_no_crea_otra_conversacion(self):
        client = _service_client("token-de-gateway")
        client.post(self.url, self._body(texto="primero"), format="json")
        response = client.post(self.url, self._body(texto="segundo"), format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["acciones"], [])  # ya no es el primer contacto

        self.assertEqual(Conversacion.objects.count(), 1)
        self.assertEqual(ConversacionLog.objects.count(), 2)

    def test_mismo_contacto_en_otro_canal_es_otro_contacto(self):
        client = _service_client("token-de-gateway")
        client.post(self.url, self._body(channel="WHATSAPP"), format="json")
        client.post(self.url, self._body(channel="MESSENGER"), format="json")
        self.assertEqual(Contact.objects.count(), 2)
        self.assertEqual(Conversacion.objects.count(), 2)

    def test_faltan_campos(self):
        response = _service_client("token-de-gateway").post(self.url, {"organization_id": self.org.id}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_organizacion_inexistente(self):
        response = _service_client("token-de-gateway").post(
            self.url, self._body(organization_id=999999), format="json",
        )
        self.assertEqual(response.status_code, 404)


class ConversacionViewSetTests(TestCase):
    def setUp(self):
        self.org = make_organization()
        self.otra_org = make_organization(name="Otra", slug="otra")
        self.operador = make_user(self.org, groups=["operadores"])
        self.otro_operador = make_user(self.org, groups=["operadores"], email="otro@test.com")
        self.admin = make_user(self.org, groups=["administradores"])

        ServiceToken.objects.create(servicio=ServiceToken.Servicio.CHANNEL_GATEWAY, token="tok", activo=True)
        gateway_client = _service_client("tok")

        gateway_client.post(
            reverse("bot-mensaje-entrante"),
            {"organization_id": self.org.id, "channel": "WHATSAPP", "contact_externo_id": "111", "texto": "hola"},
            format="json",
        )
        self.conversacion = Conversacion.objects.get()

        self.list_url = reverse("conversacion-list")

    def test_operador_ve_la_bandeja_sin_asignar(self):
        response = authenticated_client(self.operador).get(self.list_url, {"bandeja": "sin_asignar"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)

    def test_operador_de_otra_organizacion_no_la_ve(self):
        otro_operador_otra_org = make_user(self.otra_org, groups=["operadores"], email="op@otra.test")
        response = authenticated_client(otro_operador_otra_org).get(self.list_url, {"bandeja": "sin_asignar"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 0)

    def test_tomar_asigna_al_operador(self):
        url = reverse("conversacion-tomar", args=[self.conversacion.id])
        response = authenticated_client(self.operador).post(url)
        self.assertEqual(response.status_code, 200, response.data)
        self.conversacion.refresh_from_db()
        self.assertEqual(self.conversacion.operador, self.operador)

    def test_no_se_puede_tomar_dos_veces(self):
        self.conversacion.operador = self.operador
        self.conversacion.save(update_fields=["operador"])
        url = reverse("conversacion-tomar", args=[self.conversacion.id])
        response = authenticated_client(self.otro_operador).post(url)
        self.assertEqual(response.status_code, 400)

    def test_mensajes_devuelve_el_hilo(self):
        url = reverse("conversacion-mensajes", args=[self.conversacion.id])
        response = authenticated_client(self.operador).get(url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["remitente"], "CONTACTO")

    @patch("conversations.views.enviar_mensaje_saliente", return_value=True)
    def test_responder_requiere_haberla_tomado(self, mock_enviar):
        url = reverse("conversacion-responder", args=[self.conversacion.id])
        response = authenticated_client(self.operador).post(url, {"texto": "Hola, ¿en qué te ayudo?"})
        self.assertEqual(response.status_code, 403)
        mock_enviar.assert_not_called()

    @patch("conversations.views.enviar_mensaje_saliente", return_value=True)
    def test_responder_manda_el_mensaje_y_lo_loguea(self, mock_enviar):
        self.conversacion.operador = self.operador
        self.conversacion.save(update_fields=["operador"])
        url = reverse("conversacion-responder", args=[self.conversacion.id])
        response = authenticated_client(self.operador).post(url, {"texto": "Hola, ¿en qué te ayudo?"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["entregado"])
        mock_enviar.assert_called_once_with(self.conversacion, "Hola, ¿en qué te ayudo?")
        self.assertEqual(ConversacionLog.objects.filter(remitente="OPERADOR").count(), 1)

    @patch("conversations.views.enviar_mensaje_saliente", return_value=True)
    def test_cerrar_manda_despedida_y_cambia_estado(self, mock_enviar):
        self.conversacion.operador = self.operador
        self.conversacion.save(update_fields=["operador"])
        url = reverse("conversacion-cerrar", args=[self.conversacion.id])
        response = authenticated_client(self.operador).post(url)
        self.assertEqual(response.status_code, 200, response.data)
        self.conversacion.refresh_from_db()
        self.assertEqual(self.conversacion.estado, Conversacion.Estado.CERRADA)
        self.assertIsNotNone(self.conversacion.cerrada_at)
        mock_enviar.assert_called_once()
        self.assertTrue(ConversacionLog.objects.filter(remitente="SISTEMA").exists())

    def test_admin_no_puede_gestionar_sin_organization_es_bloqueado_igual_que_siempre(self):
        superusuario = make_user(
            None, groups=["superusuarios"], email="superusuario@plataforma.test",
            is_staff=True, is_superuser=True,
        )
        response = authenticated_client(superusuario).get(self.list_url)
        self.assertEqual(response.status_code, 403)


class MenuEngineTests(TestCase):
    """Recorrido real del árbol de `MenuOpcion` a través de `POST /api/core/
    bot/mensaje-entrante/` — un mensaje de texto por vez, como llegaría
    normalizado desde Channel Gateway."""

    def setUp(self):
        self.org = make_organization()
        self.team_ventas = Team.objects.create(organization=self.org, name="Ventas")
        ServiceToken.objects.create(servicio=ServiceToken.Servicio.CHANNEL_GATEWAY, token="tok", activo=True)
        self.client_gateway = _service_client("tok")
        self.url = reverse("bot-mensaje-entrante")

        # Raíz: 1) Ventas (submenú) -> 1) Precios (respuesta), 2) Volver
        #       2) Hablar con un operador (derivación a Ventas)
        #       3) Salir (terminar)
        self.ventas = MenuOpcion.objects.create(
            organization=self.org, texto="Ventas", orden=1, tipo=MenuOpcion.Tipo.SUBMENU,
        )
        MenuOpcion.objects.create(
            organization=self.org, parent=self.ventas, texto="Precios", orden=1,
            tipo=MenuOpcion.Tipo.RESPUESTA, respuesta_texto="Nuestros precios arrancan en $100.",
        )
        MenuOpcion.objects.create(
            organization=self.org, parent=self.ventas, texto="Volver", orden=2, tipo=MenuOpcion.Tipo.VOLVER,
        )
        MenuOpcion.objects.create(
            organization=self.org, texto="Hablar con un operador", orden=2,
            tipo=MenuOpcion.Tipo.DERIVACION, team=self.team_ventas,
        )
        MenuOpcion.objects.create(organization=self.org, texto="Salir", orden=3, tipo=MenuOpcion.Tipo.TERMINAR)

    def _mandar(self, texto, contacto="5491111111111"):
        return self.client_gateway.post(
            self.url,
            {"organization_id": self.org.id, "channel": "WHATSAPP", "contact_externo_id": contacto, "texto": texto},
            format="json",
        )

    def test_primer_mensaje_manda_bienvenida_y_menu_principal(self):
        response = self._mandar("hola")
        self.assertEqual(response.status_code, 200, response.data)
        acciones = response.data["acciones"]
        self.assertEqual(len(acciones), 2)
        self.assertIn("1. Ventas", acciones[1]["texto"])
        self.assertIn("2. Hablar con un operador", acciones[1]["texto"])
        self.assertIn("3. Salir", acciones[1]["texto"])
        conversacion = Conversacion.objects.get()
        self.assertFalse(conversacion.menu_finalizado)
        self.assertIsNone(conversacion.nodo_menu_actual)

    def test_elegir_submenu_muestra_sus_opciones(self):
        self._mandar("hola")
        response = self._mandar("1")
        self.assertEqual(response.status_code, 200, response.data)
        acciones = response.data["acciones"]
        self.assertEqual(len(acciones), 1)
        self.assertIn("1. Precios", acciones[0]["texto"])
        self.assertIn("2. Volver", acciones[0]["texto"])
        conversacion = Conversacion.objects.get()
        self.assertEqual(conversacion.nodo_menu_actual, self.ventas)
        self.assertFalse(conversacion.menu_finalizado)

    def test_elegir_respuesta_manda_el_texto_y_vuelve_a_mostrar_el_menu(self):
        self._mandar("hola")
        self._mandar("1")  # entra a Ventas
        response = self._mandar("1")  # Precios
        self.assertEqual(response.status_code, 200, response.data)
        acciones = response.data["acciones"]
        self.assertEqual(len(acciones), 2)
        self.assertIn("$100", acciones[0]["texto"])
        self.assertIn("1. Precios", acciones[1]["texto"])
        conversacion = Conversacion.objects.get()
        self.assertFalse(conversacion.menu_finalizado)
        self.assertEqual(conversacion.nodo_menu_actual, self.ventas)

    def test_volver_sube_un_nivel(self):
        self._mandar("hola")
        self._mandar("1")  # entra a Ventas
        response = self._mandar("2")  # Volver
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("1. Ventas", response.data["acciones"][0]["texto"])
        conversacion = Conversacion.objects.get()
        self.assertIsNone(conversacion.nodo_menu_actual)

    def test_derivacion_asigna_equipo_y_termina_el_menu(self):
        self._mandar("hola")
        response = self._mandar("2")  # Hablar con un operador
        self.assertEqual(response.status_code, 200, response.data)
        conversacion = Conversacion.objects.get()
        self.assertEqual(conversacion.team, self.team_ventas)
        self.assertTrue(conversacion.menu_finalizado)
        self.assertEqual(conversacion.estado, Conversacion.Estado.ABIERTA)  # sigue abierta, en la bandeja

    def test_despues_de_la_derivacion_los_mensajes_no_se_interpretan_como_menu(self):
        self._mandar("hola")
        self._mandar("2")  # deriva
        response = self._mandar("cualquier cosa")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["acciones"], [])
        self.assertEqual(ConversacionLog.objects.filter(remitente="CONTACTO").count(), 3)

    def test_terminar_cierra_la_conversacion(self):
        self._mandar("hola")
        response = self._mandar("3")  # Salir
        self.assertEqual(response.status_code, 200, response.data)
        conversacion = Conversacion.objects.get()
        self.assertEqual(conversacion.estado, Conversacion.Estado.CERRADA)
        self.assertIsNotNone(conversacion.cerrada_at)
        self.assertTrue(conversacion.menu_finalizado)

    def test_opcion_invalida_repite_el_menu_actual(self):
        self._mandar("hola")
        response = self._mandar("99")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("No entendí", response.data["acciones"][0]["texto"])
        self.assertIn("1. Ventas", response.data["acciones"][0]["texto"])

    def test_texto_no_numerico_tambien_repite_el_menu(self):
        self._mandar("hola")
        response = self._mandar("no sé qué elegir")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("No entendí", response.data["acciones"][0]["texto"])

    def test_una_vez_tomada_por_un_operador_no_hay_mas_respuesta_automatica(self):
        self._mandar("hola")
        conversacion = Conversacion.objects.get()
        operador = make_user(self.org, groups=["operadores"])
        conversacion.operador = operador
        conversacion.save(update_fields=["operador"])

        response = self._mandar("1")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["acciones"], [])

    def test_organizacion_sin_menu_configurado_pasa_directo_a_la_bandeja(self):
        otra_org = make_organization(name="Sin menú", slug="sin-menu")
        response = self.client_gateway.post(
            self.url,
            {"organization_id": otra_org.id, "channel": "WHATSAPP", "contact_externo_id": "5492222222222", "texto": "hola"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        acciones = response.data["acciones"]
        self.assertEqual(len(acciones), 1)  # sólo la bienvenida, no hay menú que mostrar
        conversacion = Conversacion.objects.get(organization=otra_org)
        self.assertTrue(conversacion.menu_finalizado)

    def test_organizacion_con_menu_desactivado_pasa_directo_a_la_bandeja(self):
        BotMessages.objects.create(organization=self.org, menu_activo=False)
        response = self._mandar("hola")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["acciones"]), 1)
        conversacion = Conversacion.objects.get()
        self.assertTrue(conversacion.menu_finalizado)
