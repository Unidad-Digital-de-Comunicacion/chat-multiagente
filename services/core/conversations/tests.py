from datetime import datetime, timedelta
from unittest.mock import patch

from bot_settings.models import BotMessages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from menu.models import MenuOpcion
from requests.exceptions import RequestException
from teams.models import Team

from common.test_utils import authenticated_client, make_organization, make_service_token, make_user
from platform_admin.models import ServiceToken
from rest_framework.test import APIClient

from tags.defaults import asegurar_etiquetas_sistema
from tags.models import Etiqueta

from channels.models import Canal

from .asignacion import asignar_round_robin
from .channel_gateway_client import MENSAJE_NO_ENVIADO, enviar_con_reintentos
from .conversation_engine_client import notificar_evento
from .models import (
    Contact, Conversacion, ConversacionEtiqueta, ConversacionLog, ConversacionNotaInterna, ConversacionObservacion,
    EnvioSaliente,
)


def _service_client(token):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Service-Token {token}")
    return client


class MensajeEntranteViewTests(TestCase):
    def setUp(self):
        self.org = make_organization()
        make_service_token(ServiceToken.Servicio.CHANNEL_GATEWAY, "token-de-gateway", activo=True)
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

        # Un log por cada lado: lo que escribió el contacto, y lo que le
        # contestó el bot — antes de esto, sólo quedaba el primero.
        self.assertEqual(ConversacionLog.objects.count(), 2)
        log_contacto = ConversacionLog.objects.get(remitente=ConversacionLog.Remitente.CONTACTO)
        self.assertEqual(log_contacto.texto, "Hola, quería consultar")
        log_sistema = ConversacionLog.objects.get(remitente=ConversacionLog.Remitente.SISTEMA)
        self.assertEqual(log_sistema.texto, response.data["acciones"][0]["texto"])

    def test_segundo_mensaje_del_mismo_contacto_no_crea_otra_conversacion(self):
        client = _service_client("token-de-gateway")
        client.post(self.url, self._body(texto="primero"), format="json")
        response = client.post(self.url, self._body(texto="segundo"), format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["acciones"], [])  # ya no es el primer contacto

        self.assertEqual(Conversacion.objects.count(), 1)
        # 2 mensajes del contacto + la bienvenida que el bot mandó una sola
        # vez, en el primero (el segundo no generó respuesta automática).
        self.assertEqual(ConversacionLog.objects.filter(remitente="CONTACTO").count(), 2)
        self.assertEqual(ConversacionLog.objects.filter(remitente="SISTEMA").count(), 1)

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

        make_service_token(ServiceToken.Servicio.CHANNEL_GATEWAY, "tok", activo=True)
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

    def test_no_se_puede_tomar_mientras_el_lock_de_otro_siga_vigente(self):
        self.conversacion.operador = self.operador
        self.conversacion.bloqueada_hasta = timezone.now() + timedelta(minutes=2)
        self.conversacion.save(update_fields=["operador", "bloqueada_hasta"])
        url = reverse("conversacion-tomar", args=[self.conversacion.id])
        response = authenticated_client(self.otro_operador).post(url)
        self.assertEqual(response.status_code, 400)

    def test_se_puede_reclamar_una_vez_que_el_lock_vencio(self):
        self.conversacion.operador = self.operador
        self.conversacion.bloqueada_hasta = timezone.now() - timedelta(minutes=1)  # ya venció
        self.conversacion.save(update_fields=["operador", "bloqueada_hasta"])
        url = reverse("conversacion-tomar", args=[self.conversacion.id])
        response = authenticated_client(self.otro_operador).post(url)
        self.assertEqual(response.status_code, 200, response.data)
        self.conversacion.refresh_from_db()
        self.assertEqual(self.conversacion.operador, self.otro_operador)

    def test_tomar_pone_un_lock_de_2_minutos(self):
        url = reverse("conversacion-tomar", args=[self.conversacion.id])
        antes = timezone.now()
        authenticated_client(self.operador).post(url)
        self.conversacion.refresh_from_db()
        self.assertGreater(self.conversacion.bloqueada_hasta, antes + timedelta(minutes=1, seconds=55))
        self.assertLess(self.conversacion.bloqueada_hasta, antes + timedelta(minutes=2, seconds=5))

    def test_una_conversacion_con_lock_vencido_aparece_en_sin_asignar(self):
        self.conversacion.operador = self.operador
        self.conversacion.bloqueada_hasta = timezone.now() - timedelta(minutes=1)
        self.conversacion.save(update_fields=["operador", "bloqueada_hasta"])
        response = authenticated_client(self.otro_operador).get(self.list_url, {"bandeja": "sin_asignar"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)

    def test_mensajes_devuelve_el_hilo(self):
        url = reverse("conversacion-mensajes", args=[self.conversacion.id])
        response = authenticated_client(self.operador).get(url)
        self.assertEqual(response.status_code, 200, response.data)
        # El "hola" del setUp, más la bienvenida automática que el bot le
        # contestó (sin menú configurado en esta clase de tests).
        self.assertEqual(len(response.data), 2)
        self.assertEqual(response.data[0]["remitente"], "CONTACTO")
        self.assertEqual(response.data[1]["remitente"], "SISTEMA")

    @patch("conversations.views.enviar_con_reintentos", return_value=True)
    def test_responder_requiere_haberla_tomado(self, mock_enviar):
        url = reverse("conversacion-responder", args=[self.conversacion.id])
        response = authenticated_client(self.operador).post(url, {"texto": "Hola, ¿en qué te ayudo?"})
        self.assertEqual(response.status_code, 403)
        mock_enviar.assert_not_called()

    @patch("conversations.views.enviar_con_reintentos", return_value=True)
    def test_responder_manda_el_mensaje_y_lo_loguea(self, mock_enviar):
        self.conversacion.operador = self.operador
        self.conversacion.save(update_fields=["operador"])
        url = reverse("conversacion-responder", args=[self.conversacion.id])
        response = authenticated_client(self.operador).post(url, {"texto": "Hola, ¿en qué te ayudo?"})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["entregado"])
        mock_enviar.assert_called_once_with(self.conversacion, "Hola, ¿en qué te ayudo?")
        self.assertEqual(ConversacionLog.objects.filter(remitente="OPERADOR").count(), 1)

    @patch("conversations.views.enviar_con_reintentos", return_value=True)
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

    def test_estado_operativo_pendiente_sin_equipo_ni_operador(self):
        detail_url = reverse("conversacion-detail", args=[self.conversacion.id])
        response = authenticated_client(self.operador).get(detail_url)
        self.assertEqual(response.data["estado_operativo"], "pendiente")

    def test_estado_operativo_asignada_con_equipo_sin_operador(self):
        team = Team.objects.create(organization=self.org, name="Ventas")
        self.conversacion.team = team
        self.conversacion.save(update_fields=["team"])
        detail_url = reverse("conversacion-detail", args=[self.conversacion.id])
        response = authenticated_client(self.operador).get(detail_url)
        self.assertEqual(response.data["estado_operativo"], "asignada")

    def test_estado_operativo_tomada_con_operador(self):
        reverse_tomar = reverse("conversacion-tomar", args=[self.conversacion.id])
        authenticated_client(self.operador).post(reverse_tomar)
        detail_url = reverse("conversacion-detail", args=[self.conversacion.id])
        response = authenticated_client(self.operador).get(detail_url)
        self.assertEqual(response.data["estado_operativo"], "tomada")

    @patch("conversations.views.enviar_con_reintentos", return_value=True)
    def test_estado_operativo_cerrada(self, mock_enviar):
        self.conversacion.operador = self.operador
        self.conversacion.save(update_fields=["operador"])
        authenticated_client(self.operador).post(reverse("conversacion-cerrar", args=[self.conversacion.id]))
        detail_url = reverse("conversacion-detail", args=[self.conversacion.id])
        response = authenticated_client(self.operador).get(detail_url)
        self.assertEqual(response.data["estado_operativo"], "cerrada")


class ConversacionDerivarTests(TestCase):
    """`POST /conversaciones/{id}/derivar/` — reasignación manual a otro
    equipo, distinta de la que dispara el árbol de menú."""

    def setUp(self):
        self.org = make_organization()
        self.operador = make_user(self.org, groups=["operadores"])
        self.team_destino = Team.objects.create(organization=self.org, name="Soporte")
        make_service_token(ServiceToken.Servicio.CHANNEL_GATEWAY, "tok", activo=True)
        _service_client("tok").post(
            reverse("bot-mensaje-entrante"),
            {"organization_id": self.org.id, "channel": "WHATSAPP", "contact_externo_id": "111", "texto": "hola"},
            format="json",
        )
        self.conversacion = Conversacion.objects.get()
        self.conversacion.operador = self.operador
        self.conversacion.save(update_fields=["operador"])
        self.url = reverse("conversacion-derivar", args=[self.conversacion.id])

    def test_deriva_y_deja_libre_para_el_equipo_destino(self):
        response = authenticated_client(self.operador).post(
            self.url, {"team": self.team_destino.id, "observacion": "No es mi área, pasa a Soporte."},
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.conversacion.refresh_from_db()
        self.assertEqual(self.conversacion.team, self.team_destino)
        self.assertIsNone(self.conversacion.operador)
        self.assertIsNone(self.conversacion.bloqueada_hasta)
        self.assertEqual(
            ConversacionObservacion.objects.get().texto, "No es mi área, pasa a Soporte.",
        )

    def test_requiere_observacion(self):
        response = authenticated_client(self.operador).post(self.url, {"team": self.team_destino.id, "observacion": ""})
        self.assertEqual(response.status_code, 400)

    def test_no_puede_derivar_a_un_equipo_de_otra_organizacion(self):
        otra_org = make_organization(name="Otra", slug="otra")
        team_ajeno = Team.objects.create(organization=otra_org, name="Ajeno")
        response = authenticated_client(self.operador).post(
            self.url, {"team": team_ajeno.id, "observacion": "motivo"},
        )
        self.assertEqual(response.status_code, 404)

    def test_no_se_puede_derivar_una_conversacion_cerrada(self):
        self.conversacion.estado = Conversacion.Estado.CERRADA
        self.conversacion.save(update_fields=["estado"])
        response = authenticated_client(self.operador).post(
            self.url, {"team": self.team_destino.id, "observacion": "motivo"},
        )
        self.assertEqual(response.status_code, 400)


class ConversacionEtiquetasTests(TestCase):
    """`GET/POST /conversaciones/{id}/etiquetas/` y `DELETE .../etiquetas/{id}/`."""

    def setUp(self):
        self.org = make_organization()
        self.operador = make_user(self.org, groups=["operadores"])
        make_service_token(ServiceToken.Servicio.CHANNEL_GATEWAY, "tok", activo=True)
        _service_client("tok").post(
            reverse("bot-mensaje-entrante"),
            {"organization_id": self.org.id, "channel": "WHATSAPP", "contact_externo_id": "111", "texto": "hola"},
            format="json",
        )
        self.conversacion = Conversacion.objects.get()
        self.url = reverse("conversacion-etiquetas", args=[self.conversacion.id])
        # Dispara la autogeneración del catálogo de sistema (mismo patrón
        # lazy que `tags.EtiquetaViewSet.get_queryset`).
        asegurar_etiquetas_sistema(self.org.id)
        self.en_proceso = Etiqueta.objects.get(organization=self.org, codigo="en_proceso")
        self.resuelto = Etiqueta.objects.get(organization=self.org, codigo="resuelto")
        self.general = Etiqueta.objects.create(organization=self.org, nombre="VIP", color="#000000")

    def test_aplica_una_etiqueta_general(self):
        response = authenticated_client(self.operador).post(self.url, {"etiqueta": self.general.id})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(ConversacionEtiqueta.objects.get().etiqueta, self.general)

    def test_aplicar_etiqueta_de_sistema_saca_la_etiqueta_de_sistema_anterior(self):
        authenticated_client(self.operador).post(self.url, {"etiqueta": self.en_proceso.id})
        authenticated_client(self.operador).post(self.url, {"etiqueta": self.resuelto.id, "observacion": "Resuelto ok."})
        codigos = set(ConversacionEtiqueta.objects.values_list("etiqueta__codigo", flat=True))
        self.assertEqual(codigos, {"resuelto"})

    def test_etiqueta_de_sistema_general_no_saca_la_de_equipo_ni_la_general(self):
        authenticated_client(self.operador).post(self.url, {"etiqueta": self.general.id})
        authenticated_client(self.operador).post(self.url, {"etiqueta": self.en_proceso.id})
        codigos_o_nombres = set(ConversacionEtiqueta.objects.values_list("etiqueta__nombre", flat=True))
        self.assertEqual(codigos_o_nombres, {"VIP", "En proceso"})

    def test_resolver_sin_observacion_falla(self):
        response = authenticated_client(self.operador).post(self.url, {"etiqueta": self.resuelto.id})
        self.assertEqual(response.status_code, 400)
        self.assertIn("observacion", response.data["error"]["detail"])
        self.assertEqual(ConversacionEtiqueta.objects.count(), 0)

    def test_resolver_con_observacion_la_crea_tambien(self):
        authenticated_client(self.operador).post(
            self.url, {"etiqueta": self.resuelto.id, "observacion": "Se le dio de baja el servicio."},
        )
        self.assertEqual(
            ConversacionObservacion.objects.get().texto, "Se le dio de baja el servicio.",
        )

    def test_etiqueta_general_no_exige_observacion(self):
        response = authenticated_client(self.operador).post(self.url, {"etiqueta": self.general.id})
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(ConversacionObservacion.objects.count(), 0)

    def test_no_puede_aplicar_una_etiqueta_de_otra_organizacion(self):
        otra_org = make_organization(name="Otra", slug="otra")
        etiqueta_ajena = Etiqueta.objects.create(organization=otra_org, nombre="Ajena")
        response = authenticated_client(self.operador).post(self.url, {"etiqueta": etiqueta_ajena.id})
        self.assertEqual(response.status_code, 404)

    def test_quita_una_etiqueta_aplicada(self):
        authenticated_client(self.operador).post(self.url, {"etiqueta": self.general.id})
        aplicada = ConversacionEtiqueta.objects.get()
        quitar_url = reverse("conversacion-quitar-etiqueta", args=[self.conversacion.id, aplicada.etiqueta_id])
        response = authenticated_client(self.operador).delete(quitar_url)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(ConversacionEtiqueta.objects.count(), 0)

    def test_quitar_una_etiqueta_no_aplicada_da_404(self):
        quitar_url = reverse("conversacion-quitar-etiqueta", args=[self.conversacion.id, self.general.id])
        response = authenticated_client(self.operador).delete(quitar_url)
        self.assertEqual(response.status_code, 404)

    def test_lista_las_etiquetas_aplicadas_con_su_color(self):
        authenticated_client(self.operador).post(self.url, {"etiqueta": self.general.id})
        response = authenticated_client(self.operador).get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["etiqueta"]["color"], "#000000")


class ConversacionObservacionesTests(TestCase):
    def setUp(self):
        self.org = make_organization()
        self.operador = make_user(self.org, groups=["operadores"])
        make_service_token(ServiceToken.Servicio.CHANNEL_GATEWAY, "tok", activo=True)
        _service_client("tok").post(
            reverse("bot-mensaje-entrante"),
            {"organization_id": self.org.id, "channel": "WHATSAPP", "contact_externo_id": "111", "texto": "hola"},
            format="json",
        )
        self.conversacion = Conversacion.objects.get()
        self.url = reverse("conversacion-observaciones", args=[self.conversacion.id])

    def test_agrega_y_lista_una_observacion(self):
        response = authenticated_client(self.operador).post(self.url, {"texto": "Cliente pidió que lo llamen."})
        self.assertEqual(response.status_code, 201, response.data)
        response = authenticated_client(self.operador).get(self.url)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["texto"], "Cliente pidió que lo llamen.")
        self.assertEqual(response.data[0]["operador_email"], self.operador.email)

    def test_texto_vacio_falla(self):
        response = authenticated_client(self.operador).post(self.url, {"texto": "   "})
        self.assertEqual(response.status_code, 400)


class ConversacionNotasInternasTests(TestCase):
    """Hilo de mensajería entre operadores sobre una conversación puntual —
    nunca sale hacia Channel Gateway ni la ve el contacto."""

    def setUp(self):
        self.org = make_organization()
        self.operador = make_user(self.org, groups=["operadores"])
        self.otro_operador = make_user(self.org, groups=["operadores"], email="otro@test.com")
        make_service_token(ServiceToken.Servicio.CHANNEL_GATEWAY, "tok", activo=True)
        _service_client("tok").post(
            reverse("bot-mensaje-entrante"),
            {"organization_id": self.org.id, "channel": "WHATSAPP", "contact_externo_id": "111", "texto": "hola"},
            format="json",
        )
        self.conversacion = Conversacion.objects.get()
        self.url = reverse("conversacion-notas-internas", args=[self.conversacion.id])

    def test_agrega_y_lista_una_nota_interna(self):
        authenticated_client(self.operador).post(self.url, {"texto": "¿Alguien habló con este cliente antes?"})
        response = authenticated_client(self.otro_operador).get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["operador_email"], self.operador.email)

    def test_no_queda_en_el_log_que_ve_el_contacto(self):
        authenticated_client(self.operador).post(self.url, {"texto": "nota interna"})
        self.assertEqual(ConversacionNotaInterna.objects.count(), 1)
        self.assertFalse(ConversacionLog.objects.filter(texto="nota interna").exists())


class MenuEngineTests(TestCase):
    """Recorrido real del árbol de `MenuOpcion` a través de `POST /api/core/
    bot/mensaje-entrante/` — un mensaje de texto por vez, como llegaría
    normalizado desde Channel Gateway."""

    def setUp(self):
        self.org = make_organization()
        self.team_ventas = Team.objects.create(organization=self.org, name="Ventas")
        make_service_token(ServiceToken.Servicio.CHANNEL_GATEWAY, "tok", activo=True)
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
        self.assertEqual(acciones[0]["tipo"], "enviar_texto")
        self.assertIn("1. Ventas", acciones[1]["texto"])
        self.assertIn("2. Hablar con un operador", acciones[1]["texto"])
        self.assertIn("3. Salir", acciones[1]["texto"])
        conversacion = Conversacion.objects.get()
        self.assertFalse(conversacion.menu_finalizado)
        self.assertIsNone(conversacion.nodo_menu_actual)

    def test_el_menu_se_manda_como_accion_estructurada(self):
        # Contrato de la sección 4.1.1: además del texto plano numerado
        # (fallback universal), Core manda `opciones: [{id, titulo}]` y un
        # `encabezado` sin numerar, para que Channel Gateway arme un widget
        # nativo (WhatsApp list/button) en vez de texto plano si el canal
        # y la cantidad de opciones lo permiten.
        response = self._mandar("hola")
        menu_accion = response.data["acciones"][1]
        self.assertEqual(menu_accion["tipo"], "mostrar_menu")
        self.assertNotIn("1.", menu_accion["encabezado"])
        self.assertEqual(
            menu_accion["opciones"],
            [
                {"id": "1", "titulo": "Ventas"},
                {"id": "2", "titulo": "Hablar con un operador"},
                {"id": "3", "titulo": "Salir"},
            ],
        )

    def test_elegir_por_id_de_opcion_nativa_funciona_igual_que_escribir_el_numero(self):
        # Cuando el contacto toca una fila/botón nativo en vez de escribir
        # el número a mano, Channel Gateway normaliza esa respuesta al
        # mismo `id` ("1", "2"...) — este test confirma que el motor de
        # menú lo interpreta exactamente igual.
        self._mandar("hola")
        response = self._mandar("1")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn("1. Precios", response.data["acciones"][0]["texto"])

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
        # `team_ventas` no tiene miembros activos en este setUp -> nadie a
        # quien asignar por round-robin, la conversación queda en la
        # bandeja general del equipo (ver test de abajo para el caso con
        # miembros).
        self._mandar("hola")
        response = self._mandar("2")  # Hablar con un operador
        self.assertEqual(response.status_code, 200, response.data)
        conversacion = Conversacion.objects.get()
        self.assertEqual(conversacion.team, self.team_ventas)
        self.assertTrue(conversacion.menu_finalizado)
        self.assertEqual(conversacion.estado, Conversacion.Estado.ABIERTA)  # sigue abierta, en la bandeja
        self.assertIsNone(conversacion.operador)
        self.assertIsNone(conversacion.bloqueada_hasta)

    def test_derivacion_con_equipo_con_miembro_asigna_por_round_robin(self):
        operador = make_user(self.org, groups=["operadores"])
        self.team_ventas.members.add(operador)
        self._mandar("hola")
        response = self._mandar("2")  # Hablar con un operador
        self.assertEqual(response.status_code, 200, response.data)
        conversacion = Conversacion.objects.get()
        self.assertEqual(conversacion.operador, operador)
        self.assertIsNotNone(conversacion.bloqueada_hasta)
        self.assertGreater(conversacion.bloqueada_hasta, timezone.now())

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

    def test_cada_accion_saliente_queda_registrada_en_el_log(self):
        # Antes de esto, sólo se guardaba lo que escribía el contacto — nada
        # de lo que el bot mandaba de vuelta.
        self._mandar("hola")  # bienvenida + menú principal -> 2 salientes
        self._mandar("1")  # entra a Ventas (submenú) -> 1 saliente
        self._mandar("1")  # dentro de Ventas: Precios (respuesta) + vuelve a mostrar Ventas -> 2 salientes
        self._mandar("2")  # dentro de Ventas: Volver -> sube al menú principal -> 1 saliente

        logs_sistema = list(ConversacionLog.objects.filter(remitente="SISTEMA").order_by("creado_at"))
        # bienvenida, menú principal, submenú Ventas, precios, menú Ventas de nuevo, menú principal de nuevo
        self.assertEqual(len(logs_sistema), 6)
        self.assertIn("$100", logs_sistema[3].texto)

        conversacion = Conversacion.objects.get()
        self.assertFalse(conversacion.menu_finalizado)  # "Volver" no termina el menú, sigue en modo bot
        self.assertIsNone(conversacion.nodo_menu_actual)  # de vuelta en la raíz

        # El primer registro del hilo siempre es lo que escribió el
        # contacto — nunca puede haber una respuesta del bot sin que algo
        # la haya disparado antes.
        todos = list(ConversacionLog.objects.order_by("creado_at").values_list("remitente", flat=True))
        self.assertEqual(todos[0], "CONTACTO")


class AsignacionRoundRobinTests(TestCase):
    """`asignar_round_robin` en aislamiento, sin pasar por el motor de menú
    ni por la vista — todo se recalcula del estado real de `Conversacion`
    en cada llamada (ver docstring de `asignacion.py`), así que estos tests
    arman ese estado a mano."""

    def setUp(self):
        self.org = make_organization()
        self.team = Team.objects.create(organization=self.org, name="Ventas")
        self.contact = Contact.objects.create(organization=self.org, canal="WHATSAPP", identificador_externo="123")

    def _conversacion_abierta(self, operador):
        return Conversacion.objects.create(
            organization=self.org, contact=self.contact, canal="WHATSAPP",
            operador=operador, estado=Conversacion.Estado.ABIERTA,
        )

    def test_equipo_sin_miembros_devuelve_none(self):
        self.assertIsNone(asignar_round_robin(self.team))

    def test_equipo_none_devuelve_none(self):
        self.assertIsNone(asignar_round_robin(None))

    def test_miembro_inactivo_no_se_considera(self):
        inactivo = make_user(self.org, groups=["operadores"])
        inactivo.is_active = False
        inactivo.save(update_fields=["is_active"])
        self.team.members.add(inactivo)
        self.assertIsNone(asignar_round_robin(self.team))

    def test_con_un_solo_miembro_activo_lo_elige_sin_importar_su_carga(self):
        operador = make_user(self.org, groups=["operadores"])
        self.team.members.add(operador)
        for _ in range(3):
            self._conversacion_abierta(operador)
        self.assertEqual(asignar_round_robin(self.team), operador)

    def test_elige_al_miembro_con_menos_conversaciones_abiertas(self):
        ocupado = make_user(self.org, groups=["operadores"], email="ocupado@test.com")
        libre = make_user(self.org, groups=["operadores"], email="libre@test.com")
        self.team.members.add(ocupado, libre)
        self._conversacion_abierta(ocupado)
        self._conversacion_abierta(ocupado)
        self.assertEqual(asignar_round_robin(self.team), libre)

    def test_conversaciones_cerradas_no_cuentan_como_carga(self):
        con_cerradas = make_user(self.org, groups=["operadores"], email="con-cerradas@test.com")
        sin_nada = make_user(self.org, groups=["operadores"], email="sin-nada@test.com")
        self.team.members.add(con_cerradas, sin_nada)
        cerrada = self._conversacion_abierta(con_cerradas)
        cerrada.estado = Conversacion.Estado.CERRADA
        cerrada.save(update_fields=["estado"])
        # Empatados en 0 abiertas -> desempata por id (el primero en orden
        # de creación), no importa cuál de los dos tenga conversaciones
        # cerradas en su historial.
        self.assertEqual(asignar_round_robin(self.team), con_cerradas)

    def test_empate_desempata_por_id_de_forma_estable(self):
        primero = make_user(self.org, groups=["operadores"], email="primero@test.com")
        segundo = make_user(self.org, groups=["operadores"], email="segundo@test.com")
        self.team.members.add(segundo, primero)  # orden de alta invertido
        self.assertEqual(asignar_round_robin(self.team), primero)


class NotificarEventoTests(TestCase):
    """`conversation_engine_client.notificar_evento` en aislamiento — mejor
    esfuerzo: nunca debe levantar, con o sin Conversation Engine configurado
    o disponible."""

    def setUp(self):
        self.org = make_organization()

    @patch("conversations.conversation_engine_client.requests.post")
    def test_sin_token_activo_no_intenta_nada(self, mock_post):
        notificar_evento(tipo="mensaje_nuevo", organization_id=self.org.id, conversacion_id=1)
        mock_post.assert_not_called()

    @patch("conversations.conversation_engine_client.requests.post")
    def test_con_token_activo_manda_el_evento(self, mock_post):
        make_service_token(ServiceToken.Servicio.CONVERSATION_ENGINE, "tok-ce", activo=True)
        notificar_evento(
            tipo="conversacion_actualizada", organization_id=self.org.id, conversacion_id=7,
            team_id=3, operador_id=None,
        )
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Service-Token tok-ce")
        self.assertEqual(
            kwargs["json"],
            {"tipo": "conversacion_actualizada", "organization_id": self.org.id, "conversacion_id": 7, "team_id": 3, "operador_id": None},
        )

    @patch("conversations.conversation_engine_client.requests.post")
    def test_token_inactivo_no_intenta_nada(self, mock_post):
        make_service_token(ServiceToken.Servicio.CONVERSATION_ENGINE, "tok-ce", activo=False)
        notificar_evento(tipo="mensaje_nuevo", organization_id=self.org.id, conversacion_id=1)
        mock_post.assert_not_called()

    @patch("conversations.conversation_engine_client.requests.post", side_effect=RequestException("caído"))
    def test_si_falla_la_request_no_propaga_la_excepcion(self, mock_post):
        make_service_token(ServiceToken.Servicio.CONVERSATION_ENGINE, "tok-ce", activo=True)
        notificar_evento(tipo="mensaje_nuevo", organization_id=self.org.id, conversacion_id=1)  # no debe levantar


class NotificarEventoEnLasActionsTests(TestCase):
    """Confirma que las actions que cambian la bandeja avisan a Conversation
    Engine — el contenido exacto del evento ya está cubierto arriba, acá
    sólo importa CUÁNDO se dispara."""

    def setUp(self):
        self.org = make_organization()
        self.operador = make_user(self.org, groups=["operadores"])
        make_service_token(ServiceToken.Servicio.CHANNEL_GATEWAY, "tok", activo=True)
        _service_client("tok").post(
            reverse("bot-mensaje-entrante"),
            {"organization_id": self.org.id, "channel": "WHATSAPP", "contact_externo_id": "111", "texto": "hola"},
            format="json",
        )
        self.conversacion = Conversacion.objects.get()

    @patch("conversations.views.notificar_evento")
    def test_mensaje_entrante_avisa(self, mock_notificar):
        mock_notificar.reset_mock()
        _service_client("tok").post(
            reverse("bot-mensaje-entrante"),
            {"organization_id": self.org.id, "channel": "WHATSAPP", "contact_externo_id": "111", "texto": "otro mensaje"},
            format="json",
        )
        mock_notificar.assert_called_once()
        self.assertEqual(mock_notificar.call_args.kwargs["tipo"], "mensaje_nuevo")

    @patch("conversations.views.notificar_evento")
    def test_tomar_avisa(self, mock_notificar):
        url = reverse("conversacion-tomar", args=[self.conversacion.id])
        authenticated_client(self.operador).post(url)
        mock_notificar.assert_called_once()
        self.assertEqual(mock_notificar.call_args.kwargs["tipo"], "conversacion_actualizada")

    @patch("conversations.views.notificar_evento")
    def test_notas_internas_avisa(self, mock_notificar):
        url = reverse("conversacion-notas-internas", args=[self.conversacion.id])
        authenticated_client(self.operador).post(url, {"texto": "nota"})
        mock_notificar.assert_called_once()
        self.assertEqual(mock_notificar.call_args.kwargs["tipo"], "nota_interna_nueva")


class ConversacionHistorialTests(TestCase):
    """`GET /conversaciones/historial/` — vista resumida para
    `administradores` (permiso propio, `ver_historial_conversacion`,
    NO el `view_conversacion` de los operadores): sólo inicio/derivación/
    fin, nunca mensajes/etiquetas/notas."""

    def setUp(self):
        self.org = make_organization()
        self.otra_org = make_organization(name="Otra", slug="otra")
        self.admin = make_user(self.org, groups=["administradores"])
        self.operador = make_user(self.org, groups=["operadores"])
        self.team = Team.objects.create(organization=self.org, name="Ventas")
        make_service_token(ServiceToken.Servicio.CHANNEL_GATEWAY, "tok", activo=True)
        _service_client("tok").post(
            reverse("bot-mensaje-entrante"),
            {"organization_id": self.org.id, "channel": "WHATSAPP", "contact_externo_id": "111", "texto": "hola"},
            format="json",
        )
        self.conversacion = Conversacion.objects.get()
        self.url = reverse("conversacion-historial")

    def test_admin_ve_el_historial_de_su_organizacion(self):
        response = authenticated_client(self.admin).get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 1)
        fila = response.data["results"][0]
        self.assertEqual(fila["id"], self.conversacion.id)
        self.assertIn("iniciada_at", fila)
        self.assertIn("cerrada_at", fila)
        self.assertIn("derivada_at", fila)
        self.assertNotIn("mensajes", fila)

    def test_incluye_conversaciones_cerradas_a_diferencia_de_bandeja(self):
        self.conversacion.estado = Conversacion.Estado.CERRADA
        self.conversacion.cerrada_at = timezone.now()
        self.conversacion.save(update_fields=["estado", "cerrada_at"])
        response = authenticated_client(self.admin).get(self.url)
        self.assertEqual(response.data["count"], 1)

    def test_operador_no_puede_ver_el_historial(self):
        response = authenticated_client(self.operador).get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_no_ve_el_historial_de_otra_organizacion(self):
        otro_admin = make_user(self.otra_org, groups=["administradores"], email="otro-admin@test.com")
        response = authenticated_client(otro_admin).get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["count"], 0)

    def test_derivar_a_mano_actualiza_derivada_at(self):
        self.conversacion.operador = self.operador
        self.conversacion.save(update_fields=["operador"])
        url_derivar = reverse("conversacion-derivar", args=[self.conversacion.id])
        antes = timezone.now()
        authenticated_client(self.operador).post(url_derivar, {"team": self.team.id, "observacion": "motivo"})
        response = authenticated_client(self.admin).get(self.url)
        derivada_at = parse_datetime(response.data["results"][0]["derivada_at"])
        self.assertIsNotNone(derivada_at)
        self.assertGreaterEqual(derivada_at, antes)

    def test_derivacion_por_menu_actualiza_derivada_at(self):
        team_ventas = Team.objects.create(organization=self.org, name="Soporte")
        MenuOpcion.objects.create(
            organization=self.org, texto="Hablar con un operador", orden=1,
            tipo=MenuOpcion.Tipo.DERIVACION, team=team_ventas,
        )
        # Conversación nueva (la del setUp ya no tiene menú activo configurado).
        _service_client("tok").post(
            reverse("bot-mensaje-entrante"),
            {"organization_id": self.org.id, "channel": "WHATSAPP", "contact_externo_id": "222", "texto": "hola"},
            format="json",
        )
        _service_client("tok").post(
            reverse("bot-mensaje-entrante"),
            {"organization_id": self.org.id, "channel": "WHATSAPP", "contact_externo_id": "222", "texto": "1"},
            format="json",
        )
        nueva = Conversacion.objects.get(contact__identificador_externo="222")
        self.assertIsNotNone(nueva.derivada_at)


class ConversacionHistorialFiltrosTests(TestCase):
    """Filtros de `GET /conversaciones/historial/` — mismo
    `aplicar_filtros_historial` que usa la vista de plataforma, así que
    alcanza con probarlos acá una vez."""

    def setUp(self):
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        self.team_ventas = Team.objects.create(organization=self.org, name="Ventas")
        self.team_soporte = Team.objects.create(organization=self.org, name="Soporte")
        self.url = reverse("conversacion-historial")

        contacto_whatsapp = Contact.objects.create(
            organization=self.org, canal="WHATSAPP", identificador_externo="5493511234567", nombre="",
        )
        contacto_messenger = Contact.objects.create(
            organization=self.org, canal="MESSENGER", identificador_externo="psid-999", nombre="Juan Pérez",
        )
        self.conv_whatsapp_derivada = Conversacion.objects.create(
            organization=self.org, contact=contacto_whatsapp, canal="WHATSAPP", team=self.team_ventas,
        )
        self.conv_messenger_sin_derivar = Conversacion.objects.create(
            organization=self.org, contact=contacto_messenger, canal="MESSENGER",
        )
        Conversacion.objects.filter(pk=self.conv_whatsapp_derivada.pk).update(
            iniciada_at=timezone.make_aware(datetime(2026, 1, 10)),
        )
        Conversacion.objects.filter(pk=self.conv_messenger_sin_derivar.pk).update(
            iniciada_at=timezone.make_aware(datetime(2026, 6, 20)),
        )

    def test_filtra_por_canal(self):
        response = authenticated_client(self.admin).get(self.url, {"canal": "MESSENGER"})
        ids = {f["id"] for f in response.data["results"]}
        self.assertEqual(ids, {self.conv_messenger_sin_derivar.id})

    def test_canal_invalido_da_400(self):
        response = authenticated_client(self.admin).get(self.url, {"canal": "TELEGRAM"})
        self.assertEqual(response.status_code, 400)

    def test_filtra_por_team(self):
        response = authenticated_client(self.admin).get(self.url, {"team": self.team_ventas.id})
        ids = {f["id"] for f in response.data["results"]}
        self.assertEqual(ids, {self.conv_whatsapp_derivada.id})

    def test_filtra_por_derivada_true(self):
        response = authenticated_client(self.admin).get(self.url, {"derivada": "true"})
        ids = {f["id"] for f in response.data["results"]}
        self.assertEqual(ids, {self.conv_whatsapp_derivada.id})

    def test_filtra_por_derivada_false(self):
        response = authenticated_client(self.admin).get(self.url, {"derivada": "false"})
        ids = {f["id"] for f in response.data["results"]}
        self.assertEqual(ids, {self.conv_messenger_sin_derivar.id})

    def test_sin_filtro_derivada_trae_las_dos(self):
        # Regresión del bug real: `BooleanField(required=False)` sin
        # `default=None` explícito hacía que "no vino el filtro" se
        # interpretara como `derivada=False` y excluyera todo lo derivado.
        response = authenticated_client(self.admin).get(self.url)
        self.assertEqual(response.data["count"], 2)

    def test_filtra_por_rango_de_fechas(self):
        response = authenticated_client(self.admin).get(self.url, {"desde": "2026-01-01", "hasta": "2026-03-01"})
        ids = {f["id"] for f in response.data["results"]}
        self.assertEqual(ids, {self.conv_whatsapp_derivada.id})

    def test_fecha_invalida_da_400(self):
        response = authenticated_client(self.admin).get(self.url, {"desde": "no-es-una-fecha"})
        self.assertEqual(response.status_code, 400)

    def test_busca_por_telefono(self):
        response = authenticated_client(self.admin).get(self.url, {"q": "5493511234567"})
        ids = {f["id"] for f in response.data["results"]}
        self.assertEqual(ids, {self.conv_whatsapp_derivada.id})

    def test_busca_por_nombre_de_usuario(self):
        response = authenticated_client(self.admin).get(self.url, {"q": "Juan"})
        ids = {f["id"] for f in response.data["results"]}
        self.assertEqual(ids, {self.conv_messenger_sin_derivar.id})

    def test_combina_filtros(self):
        response = authenticated_client(self.admin).get(self.url, {"canal": "WHATSAPP", "derivada": "true"})
        ids = {f["id"] for f in response.data["results"]}
        self.assertEqual(ids, {self.conv_whatsapp_derivada.id})


class EnviarConReintentosTests(TestCase):
    """`channel_gateway_client.enviar_con_reintentos` — cola de auditoría
    (`EnvioSaliente`) + hasta 3 intentos con backoff corto. Bug real que
    motivó esto (2026-09-18/19, ver conversación del proyecto): un bache
    momentáneo de `CoreNoDisponible` del lado de Channel Gateway hacía que
    un mensaje de operador quedara logueado en Core pero nunca le llegara
    de verdad al contacto, sin ningún aviso — acá se verifica que 1-2
    fallas puntuales se resuelven solas, y que 3 fallas seguidas sí le
    avisan al operador en su propio hilo."""

    def setUp(self):
        self.org = make_organization()
        self.canal = Canal.objects.create(organization=self.org, tipo=Canal.Tipo.WHATSAPP, activo=True, api_key="tok")
        make_service_token(ServiceToken.Servicio.CHANNEL_GATEWAY, "tok-gateway", activo=True)
        contact = Contact.objects.create(organization=self.org, canal=Canal.Tipo.WHATSAPP, identificador_externo="5491111111111")
        self.conversacion = Conversacion.objects.create(organization=self.org, contact=contact, canal=Canal.Tipo.WHATSAPP)

    @patch("conversations.channel_gateway_client.time.sleep")
    @patch("conversations.channel_gateway_client.enviar_mensaje_saliente")
    def test_exito_al_primer_intento_no_espera_nada(self, mock_enviar, mock_sleep):
        mock_enviar.return_value = True
        resultado = enviar_con_reintentos(self.conversacion, "hola")
        self.assertTrue(resultado)
        mock_enviar.assert_called_once_with(self.conversacion, "hola")
        mock_sleep.assert_not_called()
        envio = EnvioSaliente.objects.get()
        self.assertEqual(envio.estado, EnvioSaliente.Estado.ENVIADO)
        self.assertEqual(envio.intentos, 1)
        self.assertFalse(ConversacionLog.objects.filter(texto=MENSAJE_NO_ENVIADO).exists())

    @patch("conversations.channel_gateway_client.time.sleep")
    @patch("conversations.channel_gateway_client.enviar_mensaje_saliente")
    def test_exito_al_segundo_intento_reintenta_una_vez(self, mock_enviar, mock_sleep):
        mock_enviar.side_effect = [False, True]
        resultado = enviar_con_reintentos(self.conversacion, "hola")
        self.assertTrue(resultado)
        self.assertEqual(mock_enviar.call_count, 2)
        mock_sleep.assert_called_once_with(1)
        envio = EnvioSaliente.objects.get()
        self.assertEqual(envio.estado, EnvioSaliente.Estado.ENVIADO)
        self.assertEqual(envio.intentos, 2)

    @patch("conversations.channel_gateway_client.time.sleep")
    @patch("conversations.channel_gateway_client.enviar_mensaje_saliente")
    def test_tres_fallas_avisa_al_operador_y_marca_fallido(self, mock_enviar, mock_sleep):
        mock_enviar.return_value = False
        resultado = enviar_con_reintentos(self.conversacion, "hola")
        self.assertFalse(resultado)
        self.assertEqual(mock_enviar.call_count, 3)
        self.assertEqual(mock_sleep.call_args_list, [((1,),), ((2,),)])
        envio = EnvioSaliente.objects.get()
        self.assertEqual(envio.estado, EnvioSaliente.Estado.FALLIDO)
        self.assertEqual(envio.intentos, 3)
        aviso = ConversacionLog.objects.get(texto=MENSAJE_NO_ENVIADO)
        self.assertEqual(aviso.remitente, ConversacionLog.Remitente.SISTEMA)
        self.assertEqual(aviso.conversacion, self.conversacion)
