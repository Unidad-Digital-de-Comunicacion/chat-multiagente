import json
import os
import shutil
import tempfile
from datetime import timedelta
from unittest import mock

import requests
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from common.test_utils import authenticated_client, make_organization, make_user
from users.models import User

from . import alertas, detector, logs
from .models import ChequeoSalud, Incidente


def _linea(ts, level="INFO", service="core", logger="x", msg="hola", request_id="", exc=""):
    return json.dumps({
        "ts": ts.isoformat(), "level": level, "service": service, "logger": logger, "msg": msg,
        "request_id": request_id, "exc": exc,
    }) + "\n"


class _ConLogsTemporales(TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="logs-tests-")
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        override = override_settings(LOGS_TODOS_DIR=self.dir)
        override.enable()
        self.addCleanup(override.disable)
        self.ahora = timezone.now()

    def escribir(self, servicio, *lineas, sufijo=""):
        carpeta = os.path.join(self.dir, servicio)
        os.makedirs(carpeta, exist_ok=True)
        ruta = os.path.join(carpeta, f"{servicio}.log{sufijo}")
        with open(ruta, "a", encoding="utf-8") as f:
            f.writelines(lineas)
        return ruta


class BusquedaDeLogsTests(_ConLogsTemporales):
    def test_mezcla_todos_los_servicios_en_orden_cronologico_y_filtra_por_request_id(self):
        t = self.ahora
        self.escribir("core", _linea(t - timedelta(seconds=3), msg="a", request_id="r1"),
                      _linea(t - timedelta(seconds=1), msg="c", request_id="r2"))
        self.escribir("channel-gateway", _linea(t - timedelta(seconds=2), service="channel-gateway", msg="b",
                                                request_id="r1"))

        todo = logs.buscar(desde=t - timedelta(minutes=1), hasta=t)
        self.assertEqual([r["msg"] for r in todo.lineas], ["a", "b", "c"])

        uno = logs.buscar(desde=t - timedelta(minutes=1), hasta=t, request_id="r1")
        self.assertEqual([(r["service"], r["msg"]) for r in uno.lineas], [("core", "a"), ("channel-gateway", "b")])

    def test_incluye_los_archivos_rotados_y_respeta_la_ventana_y_el_nivel(self):
        t = self.ahora
        self.escribir("core", _linea(t - timedelta(hours=2), level="ERROR", msg="viejo"), sufijo=".1")
        self.escribir("core", _linea(t - timedelta(seconds=5), level="ERROR", msg="rotado"), sufijo=".2")
        self.escribir("core", _linea(t - timedelta(seconds=1), level="INFO", msg="info"))

        r = logs.buscar(desde=t - timedelta(minutes=1), hasta=t, nivel_min="ERROR")
        self.assertEqual([x["msg"] for x in r.lineas], ["rotado"])

    def test_limite_devuelve_las_ultimas_y_marca_truncado(self):
        t = self.ahora
        self.escribir("core", *[_linea(t - timedelta(seconds=10 - i), msg=str(i)) for i in range(10)])
        r = logs.buscar(desde=t - timedelta(minutes=1), hasta=t, limite=3)
        self.assertTrue(r.truncado)
        self.assertEqual([x["msg"] for x in r.lineas], ["7", "8", "9"])


class LecturaIncrementalTests(_ConLogsTemporales):
    def test_la_primera_vez_arranca_del_final_y_despues_lee_solo_lo_nuevo(self):
        self.escribir("core", _linea(self.ahora, level="ERROR", msg="historia vieja"))
        self.assertEqual(detector.leer_lineas_nuevas(), {})

        self.escribir("core", _linea(self.ahora, msg="nuevo 1"))
        self.assertEqual([r["msg"] for r in detector.leer_lineas_nuevas()["core"]], ["nuevo 1"])
        self.assertEqual(detector.leer_lineas_nuevas(), {})

    def test_no_consume_una_linea_a_medio_escribir(self):
        ruta = self.escribir("core", _linea(self.ahora, msg="x"))
        detector.leer_lineas_nuevas()
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(_linea(self.ahora, msg="completa").rstrip("\n"))
        self.assertEqual(detector.leer_lineas_nuevas(), {})
        with open(ruta, "a", encoding="utf-8") as f:
            f.write("\n")
        self.assertEqual([r["msg"] for r in detector.leer_lineas_nuevas()["core"]], ["completa"])

    def test_despues_de_rotar_lee_el_resto_del_archivo_viejo_y_el_nuevo(self):
        ruta = self.escribir("core", _linea(self.ahora, msg="inicio"))
        detector.leer_lineas_nuevas()
        self.escribir("core", _linea(self.ahora, msg="antes de rotar"))
        os.replace(ruta, ruta + ".1")
        self.escribir("core", _linea(self.ahora, msg="despues de rotar"))

        msgs = [r["msg"] for r in detector.leer_lineas_nuevas()["core"]]
        self.assertEqual(msgs, ["antes de rotar", "despues de rotar"])


class AnalisisTests(TestCase):
    def _reg(self, **kw):
        base = {"ts": timezone.now(), "level": "INFO", "service": "core", "logger": "x", "msg": "", "request_id": "",
                "exc": ""}
        base.update(kw)
        return base

    def test_agrupa_el_mismo_error_aunque_cambien_numeros_e_ids(self):
        ocurrencias = detector.analizar({"core": [
            self._reg(level="ERROR", msg="falló envío conversación 12 a 5491122334455", request_id="a"),
            self._reg(level="ERROR", msg="falló envío conversación 98 a 5491100000000", request_id="b"),
            self._reg(level="WARNING", msg="sólo un warning"),
        ]})
        self.assertEqual(len(ocurrencias), 1)
        (oc,) = ocurrencias.values()
        self.assertEqual(oc.cantidad, 2)
        self.assertEqual(oc.request_ids, ["a", "b"])

    def test_ip_bloqueada_y_rafaga_de_logins_fallidos_son_incidentes_de_seguridad(self):
        fallidos = [self._reg(level="WARNING", logger="authentication",
                              msg=f"login fallido email=x@y.z ip=1.2.3.4 intentos={i} bloqueada={i >= 3}")
                    for i in range(1, 11)]
        with self.settings(MONITOREO_LOGIN_FALLIDOS_UMBRAL=10):
            ocurrencias = detector.analizar({"core": fallidos})
        titulos = sorted(oc.titulo for oc in ocurrencias.values())
        self.assertEqual(len(titulos), 2)
        self.assertIn("IP 1.2.3.4 bloqueada por intentos de login fallidos", titulos)
        self.assertTrue(all(oc.tipo == "seguridad" for oc in ocurrencias.values()))

    def test_ignora_el_duplicado_de_uvicorn(self):
        ocurrencias = detector.analizar({"webchat": [
            self._reg(service="webchat", level="ERROR", logger="uvicorn.error", msg="Exception in ASGI application"),
        ]})
        self.assertEqual(ocurrencias, {})


class RegistroDeIncidentesTests(_ConLogsTemporales):
    def test_suma_ocurrencias_y_reabre_uno_resuelto(self):
        self.escribir("core", "")
        detector.leer_lineas_nuevas()
        self.escribir("core", _linea(self.ahora, level="ERROR", msg="boom 1", request_id="r1"))
        detector.procesar_logs()
        incidente = Incidente.objects.get()
        self.assertEqual((incidente.ocurrencias, incidente.estado), (1, "abierto"))

        incidente.estado = "resuelto"
        incidente.notificado_at = timezone.now()
        incidente.save()
        self.escribir("core", _linea(self.ahora, level="ERROR", msg="boom 2", request_id="r2"))
        detector.procesar_logs()
        incidente.refresh_from_db()
        self.assertEqual((incidente.ocurrencias, incidente.estado), (2, "abierto"))
        self.assertIsNone(incidente.notificado_at)
        self.assertEqual(incidente.request_ids, ["r1", "r2"])


@override_settings(MONITOREO_CHEQUEOS=[("svc", "http://svc/health")], MONITOREO_FALLOS_PARA_CAIDA=2)
class ChequeosDeSaludTests(TestCase):
    def _respuesta(self, status):
        return mock.Mock(status_code=status)

    def test_abre_incidente_tras_fallos_seguidos_y_se_resuelve_solo(self):
        with mock.patch("monitoring.detector.requests.get", side_effect=requests.ConnectionError("no")):
            detector.chequear_salud()
            self.assertFalse(Incidente.objects.exists())  # 1 fallo: puede ser un parpadeo
            detector.chequear_salud()
        incidente = Incidente.objects.get()
        self.assertEqual((incidente.tipo, incidente.estado), ("caida", "abierto"))

        with mock.patch("monitoring.detector.requests.get", return_value=self._respuesta(200)):
            recuperados = detector.chequear_salud()
        incidente.refresh_from_db()
        self.assertEqual(incidente.estado, "resuelto")
        self.assertEqual(recuperados, [incidente])
        self.assertTrue(ChequeoSalud.objects.get().ok)

    def test_un_4xx_no_es_caida(self):
        with mock.patch("monitoring.detector.requests.get", return_value=self._respuesta(404)):
            detector.chequear_salud()
            detector.chequear_salud()
        self.assertFalse(Incidente.objects.exists())


@override_settings(ALERTAS_EMAIL_DESTINO=["alertas@test.local"], ALERTAS_RENOTIFICAR_MINUTOS=60,
                   ALERTAS_PANEL_URL="https://admin.test")
class AlertasPorMailTests(TestCase):
    def _incidente(self, **kw):
        ahora = timezone.now()
        datos = {"huella": "h1", "tipo": "error", "servicio": "core", "titulo": "core · x: boom", "detalle": "boom",
                 "ocurrencias": 1, "primera_vez": ahora, "ultima_vez": ahora}
        datos.update(kw)
        return Incidente.objects.create(**datos)

    def test_un_solo_mail_con_los_nuevos_y_no_repite_hasta_que_crezca_y_pase_el_tiempo(self):
        incidente = self._incidente()
        self._incidente(huella="h2", titulo="otro")
        self.assertEqual(alertas.notificar(), 2)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["alertas@test.local"])
        self.assertIn("https://admin.test/plataforma/incidentes?id=", mail.outbox[0].body)

        self.assertEqual(alertas.notificar(), 0)  # nada nuevo
        Incidente.objects.filter(pk=incidente.pk).update(ocurrencias=5)
        self.assertEqual(alertas.notificar(), 0)  # creció, pero avisado hace menos de 60 min
        Incidente.objects.filter(pk=incidente.pk).update(notificado_at=timezone.now() - timedelta(minutes=61))
        self.assertEqual(alertas.notificar(), 1)
        self.assertIn("+4 desde el último aviso", mail.outbox[-1].body)

    def test_avisa_recuperados(self):
        incidente = self._incidente(estado="resuelto", notificado_at=timezone.now())
        alertas.notificar([incidente])
        self.assertIn("Recuperado", mail.outbox[0].subject)

    @override_settings(ALERTAS_EMAIL_DESTINO=[])
    def test_sin_destinatario_no_manda_nada(self):
        self._incidente()
        self.assertEqual(alertas.notificar(), 0)
        self.assertEqual(mail.outbox, [])

    def test_si_falla_el_smtp_queda_pendiente_para_la_proxima(self):
        self._incidente()
        with mock.patch("monitoring.alertas.send_mail", side_effect=OSError("smtp caído")):
            self.assertEqual(alertas.notificar(), 0)
        self.assertEqual(alertas.pendientes_de_aviso().count(), 1)


class ApiDelPanelTests(_ConLogsTemporales):
    def setUp(self):
        super().setUp()
        self.superusuario = User.objects.create_superuser(email="plataforma@test.local", password="Contrasena-123")
        self.org = make_organization()
        self.admin_org = make_user(self.org, groups=["administradores"], email="admin@org.test")
        self.incidente = Incidente.objects.create(
            huella="h", tipo="error", servicio="core", titulo="boom", ocurrencias=1,
            primera_vez=self.ahora, ultima_vez=self.ahora,
        )

    def test_solo_el_superusuario_de_plataforma(self):
        for url in (reverse("plataforma-incidente-list"), reverse("plataforma-logs"),
                    reverse("plataforma-chequeos-salud")):
            self.assertEqual(authenticated_client(self.admin_org).get(url).status_code, 403, url)
            self.assertEqual(authenticated_client(self.superusuario).get(url).status_code, 200, url)

    def test_resolver_y_reabrir_registra_quien(self):
        url = reverse("plataforma-incidente-detail", args=[self.incidente.pk])
        cliente = authenticated_client(self.superusuario)
        r = cliente.patch(url, {"estado": "resuelto", "titulo": "no se toca"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["resuelto_por_email"], "plataforma@test.local")
        self.assertEqual(r.data["titulo"], "boom")
        r = cliente.patch(url, {"estado": "abierto"}, format="json")
        self.assertIsNone(r.data["resuelto_at"])

    def test_logs_por_request_id_y_errores_de_parametros(self):
        self.escribir("core", _linea(self.ahora - timedelta(seconds=1), msg="uno", request_id="abc"),
                      _linea(self.ahora - timedelta(seconds=1), msg="otro", request_id="zzz"))
        cliente = authenticated_client(self.superusuario)
        r = cliente.get(reverse("plataforma-logs"), {"request_id": "abc"})
        self.assertEqual([l["msg"] for l in r.data["lineas"]], ["uno"])
        self.assertEqual(r.data["servicios_disponibles"], ["core"])
        self.assertEqual(cliente.get(reverse("plataforma-logs"), {"desde": "ayer"}).status_code, 400)


class RequestIdEnLogsDeDjangoTests(TestCase):
    def test_los_4xx_de_django_request_salen_con_el_request_id(self):
        from common.observabilidad import FormatoJson

        org = make_organization()
        user = make_user(org, groups=["administradores"], email="x@org.test")
        with self.assertLogs("django.request", level="WARNING") as capturado:
            r = authenticated_client(user).get(reverse("plataforma-logs"), HTTP_X_REQUEST_ID="rid-123")
        self.assertEqual(r["X-Request-ID"], "rid-123")
        linea = json.loads(FormatoJson().format(capturado.records[0]))
        self.assertEqual(linea["request_id"], "rid-123")
