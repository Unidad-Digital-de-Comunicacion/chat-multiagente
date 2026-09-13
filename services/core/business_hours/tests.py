import datetime as dt

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from common.test_utils import authenticated_client, make_organization, make_user
from teams.models import Team

from . import services
from .models import DiaExcepcional, HorarioAtencion


def _aware(fecha, hora):
    return timezone.make_aware(dt.datetime.combine(fecha, hora))


class EstaEnHorarioTests(TestCase):
    def setUp(self):
        self.org = make_organization()

    def test_sin_horarios_cargados_siempre_esta_en_horario(self):
        self.assertTrue(services.esta_en_horario(self.org.id))

    def test_dentro_de_una_franja_cargada(self):
        lunes = dt.date(2026, 1, 5)  # lunes
        HorarioAtencion.objects.create(
            organization=self.org, dia_semana=HorarioAtencion.DiaSemana.LUNES,
            hora_inicio=dt.time(9, 0), hora_fin=dt.time(18, 0),
        )
        momento = _aware(lunes, dt.time(12, 0))
        self.assertTrue(services.esta_en_horario(self.org.id, momento))

    def test_fuera_de_la_franja_cargada(self):
        lunes = dt.date(2026, 1, 5)
        HorarioAtencion.objects.create(
            organization=self.org, dia_semana=HorarioAtencion.DiaSemana.LUNES,
            hora_inicio=dt.time(9, 0), hora_fin=dt.time(18, 0),
        )
        momento = _aware(lunes, dt.time(20, 0))
        self.assertFalse(services.esta_en_horario(self.org.id, momento))

    def test_feriado_compartido_cierra_a_toda_organizacion(self):
        lunes = dt.date(2026, 1, 5)
        HorarioAtencion.objects.create(
            organization=self.org, dia_semana=HorarioAtencion.DiaSemana.LUNES,
            hora_inicio=dt.time(9, 0), hora_fin=dt.time(18, 0),
        )
        DiaExcepcional.objects.create(organization=None, fecha=lunes, tipo=DiaExcepcional.Tipo.FERIADO)
        momento = _aware(lunes, dt.time(12, 0))
        self.assertFalse(services.esta_en_horario(self.org.id, momento))

    def test_excepcion_propia_pisa_al_feriado_compartido(self):
        lunes = dt.date(2026, 1, 5)
        HorarioAtencion.objects.create(
            organization=self.org, dia_semana=HorarioAtencion.DiaSemana.LUNES,
            hora_inicio=dt.time(9, 0), hora_fin=dt.time(18, 0),
        )
        DiaExcepcional.objects.create(organization=None, fecha=lunes, tipo=DiaExcepcional.Tipo.FERIADO)
        DiaExcepcional.objects.create(organization=self.org, fecha=lunes, tipo=DiaExcepcional.Tipo.HORARIO_REDUCIDO,
                                       hora_inicio=dt.time(10, 0), hora_fin=dt.time(13, 0))
        self.assertTrue(services.esta_en_horario(self.org.id, _aware(lunes, dt.time(11, 0))))
        self.assertFalse(services.esta_en_horario(self.org.id, _aware(lunes, dt.time(15, 0))))

    def test_otra_organizacion_no_se_ve_afectada_por_horarios_ajenos(self):
        otra = make_organization(name="Otra", slug="otra")
        lunes = dt.date(2026, 1, 5)
        HorarioAtencion.objects.create(
            organization=self.org, dia_semana=HorarioAtencion.DiaSemana.LUNES,
            hora_inicio=dt.time(9, 0), hora_fin=dt.time(18, 0),
        )
        # `otra` no cargó horarios: siempre en horario, sin importar los de `self.org`.
        self.assertTrue(services.esta_en_horario(otra.id, _aware(lunes, dt.time(3, 0))))


class ProximaAperturaTests(TestCase):
    def test_busca_hacia_adelante_hasta_encontrar_una_franja(self):
        org = make_organization()
        miercoles = dt.date(2026, 1, 7)
        HorarioAtencion.objects.create(
            organization=org, dia_semana=HorarioAtencion.DiaSemana.VIERNES,
            hora_inicio=dt.time(9, 0), hora_fin=dt.time(13, 0),
        )
        resultado = services.proxima_apertura(org.id, _aware(miercoles, dt.time(8, 0)))
        self.assertIsNotNone(resultado)
        self.assertEqual(resultado.weekday(), 4)  # viernes
        self.assertEqual(resultado.time(), dt.time(9, 0))


class TeamHorarioHabilViewTests(TestCase):
    def test_endpoint_resuelve_via_organizacion_del_equipo(self):
        org = make_organization()
        admin = make_user(org, groups=["administradores"])
        team = Team.objects.create(organization=org, name="Ventas")
        response = authenticated_client(admin).get(reverse("team-horario-habil", args=[team.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("en_horario", response.data)

    def test_no_puede_consultar_un_equipo_de_otra_organizacion(self):
        org_a = make_organization(name="Org A", slug="org-a")
        org_b = make_organization(name="Org B", slug="org-b")
        admin_a = make_user(org_a, groups=["administradores"])
        team_b = Team.objects.create(organization=org_b, name="Ventas")
        response = authenticated_client(admin_a).get(reverse("team-horario-habil", args=[team_b.id]))
        self.assertEqual(response.status_code, 403)


class HorarioAtencionViewSetTests(TestCase):
    def test_admin_no_puede_ver_ni_editar_un_horario_de_otra_organizacion_por_id(self):
        # Mismo permiso Django en los dos admins — el bloqueo lo da el
        # scoping por organización del queryset, no el permiso, que es global.
        org_a = make_organization(name="Org A", slug="org-a")
        org_b = make_organization(name="Org B", slug="org-b")
        admin_a = make_user(org_a, groups=["administradores"])
        franja_b = HorarioAtencion.objects.create(
            organization=org_b, dia_semana=HorarioAtencion.DiaSemana.LUNES,
            hora_inicio=dt.time(9, 0), hora_fin=dt.time(18, 0),
        )
        url = reverse("horario-atencion-detail", args=[franja_b.id])
        self.assertEqual(authenticated_client(admin_a).get(url).status_code, 404)
        response = authenticated_client(admin_a).delete(url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(HorarioAtencion.objects.filter(pk=franja_b.id).exists())


class DiaExcepcionalViewSetTests(TestCase):
    def test_admin_no_puede_ver_ni_editar_una_excepcion_de_otra_organizacion_por_id(self):
        org_a = make_organization(name="Org A", slug="org-a")
        org_b = make_organization(name="Org B", slug="org-b")
        admin_a = make_user(org_a, groups=["administradores"])
        excepcion_b = DiaExcepcional.objects.create(
            organization=org_b, fecha=dt.date(2026, 12, 25), tipo=DiaExcepcional.Tipo.FERIADO,
        )
        url = reverse("dia-excepcional-detail", args=[excepcion_b.id])
        self.assertEqual(authenticated_client(admin_a).get(url).status_code, 404)
        response = authenticated_client(admin_a).delete(url)
        self.assertEqual(response.status_code, 404)
        self.assertTrue(DiaExcepcional.objects.filter(pk=excepcion_b.id).exists())


class SincronizarFeriadosActionTests(TestCase):
    """POST /api/core/dias-excepcionales/sincronizar-feriados/ — se llama al
    entrar a la sección de días excepcionales del panel, para que el
    catálogo compartido de feriados del año actual y el siguiente esté
    siempre al día. Se mockea el cliente HTTP: no queremos pegarle a la API
    pública real desde los tests."""

    def setUp(self):
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        self.operador = make_user(self.org, groups=["operadores"])
        self.url = reverse("dia-excepcional-sincronizar-feriados")

    def _feriados_de(self, anio):
        return [{"fecha": f"{anio}-01-01", "tipo": "inamovible", "nombre": "Año Nuevo"}]

    def test_carga_el_anio_actual_y_el_siguiente(self):
        from unittest.mock import patch

        hoy = timezone.localdate()
        with patch("business_hours.feriados_client.obtener_feriados", side_effect=lambda anio: self._feriados_de(anio)) as mock_obtener:
            response = authenticated_client(self.admin).post(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(mock_obtener.call_count, 2)
        anios_pedidos = {call.args[0] for call in mock_obtener.call_args_list}
        self.assertEqual(anios_pedidos, {hoy.year, hoy.year + 1})
        self.assertTrue(response.data["anios"][hoy.year])
        self.assertTrue(
            DiaExcepcional.objects.filter(organization__isnull=True, fecha=dt.date(hoy.year, 1, 1)).exists()
        )
        self.assertTrue(
            DiaExcepcional.objects.filter(organization__isnull=True, fecha=dt.date(hoy.year + 1, 1, 1)).exists()
        )

    def test_no_falla_si_la_api_externa_no_responde(self):
        from unittest.mock import patch

        with patch("business_hours.feriados_client.obtener_feriados", side_effect=Exception("timeout")):
            response = authenticated_client(self.admin).post(self.url)
        self.assertEqual(response.status_code, 200, response.data)

    def test_operador_no_puede_disparar_la_sincronizacion(self):
        response = authenticated_client(self.operador).post(self.url)
        self.assertEqual(response.status_code, 403)


class HorarioAtencionGrillaTests(TestCase):
    """Grilla semanal pintable (mismo patrón que
    chatbot/templates/chatbot/lista_horarios.html): el panel manda las celdas
    pintadas y el back las convierte en franjas de HorarioAtencion."""

    def setUp(self):
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        self.operador = make_user(self.org, groups=["operadores"])
        self.url = reverse("horario-atencion-grilla")

    def test_get_devuelve_slots_y_celdas_vacio_sin_horarios_cargados(self):
        response = authenticated_client(self.admin).get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("09:00", response.data["slots"])
        self.assertEqual(response.data["celdas"], [])

    def test_post_pinta_una_franja_contigua_lunes(self):
        celdas = [f"0-{h}" for h in ["09:00", "09:30", "10:00"]]
        response = authenticated_client(self.admin).post(self.url, {"celdas": celdas}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        franja = HorarioAtencion.objects.get(organization=self.org, dia_semana=0)
        self.assertEqual(franja.hora_inicio, dt.time(9, 0))
        self.assertEqual(franja.hora_fin, dt.time(10, 30))

    def test_post_reemplaza_la_grilla_anterior_por_completo(self):
        HorarioAtencion.objects.create(
            organization=self.org, dia_semana=HorarioAtencion.DiaSemana.MARTES,
            hora_inicio=dt.time(9, 0), hora_fin=dt.time(12, 0),
        )
        response = authenticated_client(self.admin).post(self.url, {"celdas": ["0-09:00"]}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(HorarioAtencion.objects.filter(dia_semana=HorarioAtencion.DiaSemana.MARTES).exists())

    def test_get_prepinta_lo_que_ya_esta_guardado(self):
        HorarioAtencion.objects.create(
            organization=self.org, dia_semana=HorarioAtencion.DiaSemana.LUNES,
            hora_inicio=dt.time(9, 0), hora_fin=dt.time(10, 0),
        )
        response = authenticated_client(self.admin).get(self.url)
        self.assertEqual(set(response.data["celdas"]), {"0-09:00", "0-09:30"})

    def test_operador_no_puede_guardar_la_grilla(self):
        response = authenticated_client(self.operador).post(self.url, {"celdas": ["0-09:00"]}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_clave_de_celda_invalida_falla(self):
        response = authenticated_client(self.admin).post(self.url, {"celdas": ["nope"]}, format="json")
        self.assertEqual(response.status_code, 400)


class DiaExcepcionalGrillaTests(TestCase):
    """Editor de rango de días (mismo patrón que
    chatbot/templates/chatbot/calendario_excepciones.html)."""

    def setUp(self):
        self.org = make_organization()
        self.admin = make_user(self.org, groups=["administradores"])
        self.url = reverse("dia-excepcional-grilla")

    def test_get_requiere_desde_y_hasta(self):
        response = authenticated_client(self.admin).get(self.url)
        self.assertEqual(response.status_code, 400)

    def test_get_devuelve_normal_para_dias_sin_excepcion(self):
        response = authenticated_client(self.admin).get(self.url, {"desde": "2026-01-05", "hasta": "2026-01-06"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["dias"][0]["tipo"], "NORMAL")
        self.assertFalse(response.data["dias"][0]["compartido"])

    def test_get_trae_el_feriado_del_catalogo_compartido_si_no_hay_excepcion_propia(self):
        DiaExcepcional.objects.create(
            organization=None, fecha=dt.date(2026, 1, 5), tipo=DiaExcepcional.Tipo.FERIADO,
            descripcion="Año Nuevo", sincronizado=True,
        )
        response = authenticated_client(self.admin).get(self.url, {"desde": "2026-01-05", "hasta": "2026-01-05"})
        self.assertEqual(response.status_code, 200)
        dia = response.data["dias"][0]
        self.assertEqual(dia["tipo"], "FERIADO")
        self.assertEqual(dia["descripcion"], "Año Nuevo")
        self.assertTrue(dia["compartido"])

    def test_get_prioriza_la_excepcion_propia_sobre_la_del_catalogo_compartido(self):
        DiaExcepcional.objects.create(
            organization=None, fecha=dt.date(2026, 1, 5), tipo=DiaExcepcional.Tipo.FERIADO,
            descripcion="Año Nuevo", sincronizado=True,
        )
        DiaExcepcional.objects.create(
            organization=self.org, fecha=dt.date(2026, 1, 5), tipo=DiaExcepcional.Tipo.ASUETO,
            descripcion="Igual abrimos medio día",
        )
        response = authenticated_client(self.admin).get(self.url, {"desde": "2026-01-05", "hasta": "2026-01-05"})
        dia = response.data["dias"][0]
        self.assertEqual(dia["tipo"], "ASUETO")
        self.assertEqual(dia["descripcion"], "Igual abrimos medio día")
        self.assertFalse(dia["compartido"])

    def test_post_feriado_no_necesita_celdas(self):
        response = authenticated_client(self.admin).post(
            self.url, {"dias": {"2026-01-05": {"tipo": "FERIADO"}}}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        dia = DiaExcepcional.objects.get(organization=self.org, fecha=dt.date(2026, 1, 5))
        self.assertEqual(dia.tipo, DiaExcepcional.Tipo.FERIADO)
        self.assertIsNone(dia.hora_inicio)

    def test_post_horario_reducido_pinta_un_rango(self):
        response = authenticated_client(self.admin).post(
            self.url,
            {"dias": {"2026-01-05": {"tipo": "HORARIO_REDUCIDO", "celdas": ["09:00", "09:30"]}}},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        dia = DiaExcepcional.objects.get(organization=self.org, fecha=dt.date(2026, 1, 5))
        self.assertEqual((dia.hora_inicio, dia.hora_fin), (dt.time(9, 0), dt.time(10, 0)))

    def test_post_horario_reducido_sin_celdas_falla(self):
        response = authenticated_client(self.admin).post(
            self.url, {"dias": {"2026-01-05": {"tipo": "HORARIO_REDUCIDO", "celdas": []}}}, format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_post_normal_borra_la_excepcion_propia(self):
        DiaExcepcional.objects.create(organization=self.org, fecha=dt.date(2026, 1, 5), tipo=DiaExcepcional.Tipo.ASUETO)
        response = authenticated_client(self.admin).post(
            self.url, {"dias": {"2026-01-05": {"tipo": "NORMAL"}}}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(DiaExcepcional.objects.filter(organization=self.org, fecha=dt.date(2026, 1, 5)).exists())

    def test_no_toca_el_catalogo_compartido_de_feriados(self):
        DiaExcepcional.objects.create(organization=None, fecha=dt.date(2026, 1, 5), tipo=DiaExcepcional.Tipo.FERIADO)
        response = authenticated_client(self.admin).post(
            self.url, {"dias": {"2026-01-05": {"tipo": "ASUETO"}}}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(DiaExcepcional.objects.filter(organization=None, fecha=dt.date(2026, 1, 5)).exists())
        self.assertTrue(DiaExcepcional.objects.filter(organization=self.org, fecha=dt.date(2026, 1, 5)).exists())
