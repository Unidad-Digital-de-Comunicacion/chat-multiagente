import datetime as dt

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from common.test_utils import authenticated_client, make_organization, make_user
from teams.models import Team
from users.models import User

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
        admin = make_user(org, role=User.Role.ADMIN)
        team = Team.objects.create(organization=org, name="Ventas")
        response = authenticated_client(admin).get(reverse("team-horario-habil", args=[team.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn("en_horario", response.data)

    def test_no_puede_consultar_un_equipo_de_otra_organizacion(self):
        org_a = make_organization(name="Org A", slug="org-a")
        org_b = make_organization(name="Org B", slug="org-b")
        admin_a = make_user(org_a, role=User.Role.ADMIN)
        team_b = Team.objects.create(organization=org_b, name="Ventas")
        response = authenticated_client(admin_a).get(reverse("team-horario-habil", args=[team_b.id]))
        self.assertEqual(response.status_code, 403)
