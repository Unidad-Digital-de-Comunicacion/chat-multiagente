from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from common.test_utils import make_organization, make_user

from .models import LoginLockout
from .views import token_generator


class LoginLockoutTests(TestCase):
    """3 fallas seguidas desde la misma IP -> bloqueada 12hs. El helper de
    Django `self.client` no manda X-Forwarded-For por defecto, así que cada
    request de este test se identifica como la misma IP (127.0.0.1 vía
    REMOTE_ADDR) salvo que se pase explícitamente.

    El throttle `login` (10/minuto) de DRF usa el cache de Django, que NO se
    resetea entre tests como la base de datos (no participa de la
    transacción que hace rollback) — sin este `cache.clear()`, tests
    anteriores que ya pegaron varias veces a la misma IP de prueba hacen que
    éste reciba 429 del throttle en vez del 401/200 que en realidad se
    quiere probar."""

    def setUp(self):
        cache.clear()
        self.org = make_organization()
        self.user = make_user(self.org, groups=["administradores"], email="admin@lockout.test")
        self.url = reverse("auth-login")

    def _login(self, password="Contrasena-123", ip="203.0.113.10"):
        return self.client.post(self.url, {"email": self.user.email, "password": password}, HTTP_X_FORWARDED_FOR=ip)

    def test_login_correcto_no_bloquea(self):
        response = self._login()
        self.assertEqual(response.status_code, 200)

    def test_tres_fallas_bloquean_la_ip_por_12_horas(self):
        for _ in range(3):
            response = self._login(password="incorrecta")
            self.assertEqual(response.status_code, 401)

        lockout = LoginLockout.objects.get(ip_address="203.0.113.10")
        self.assertTrue(lockout.is_blocked)
        self.assertAlmostEqual(
            (lockout.blocked_until - timezone.now()).total_seconds(), 12 * 3600, delta=30,
        )

    def test_la_cuarta_vez_ya_con_la_contrasena_correcta_sigue_bloqueada(self):
        for _ in range(3):
            self._login(password="incorrecta")
        response = self._login(password="Contrasena-123")
        self.assertEqual(response.status_code, 429)

    def test_dos_fallas_no_alcanzan_para_bloquear(self):
        for _ in range(2):
            self._login(password="incorrecta")
        response = self._login(password="Contrasena-123")
        self.assertEqual(response.status_code, 200)

    def test_un_login_correcto_reinicia_el_contador_de_fallas(self):
        self._login(password="incorrecta")
        self._login(password="incorrecta")
        self._login(password="Contrasena-123")  # éxito: resetea
        self._login(password="incorrecta")
        self._login(password="incorrecta")
        response = self._login(password="Contrasena-123")
        self.assertEqual(response.status_code, 200)  # todavía no llegó a 3 fallas seguidas

    def test_otra_ip_no_se_ve_afectada_por_los_intentos_de_la_primera(self):
        for _ in range(3):
            self._login(password="incorrecta", ip="203.0.113.10")
        response = self._login(password="Contrasena-123", ip="198.51.100.20")
        self.assertEqual(response.status_code, 200)


class PasswordResetFlowTests(TestCase):
    def setUp(self):
        cache.clear()  # ídem LoginLockoutTests: el throttle "password_reset" usa el cache
        self.org = make_organization()
        self.user = make_user(self.org, groups=["administradores"], email="admin@reset.test")

    def test_pide_el_reset_siempre_devuelve_generico(self):
        response = self.client.post(reverse("auth-password-reset"), {"email": "no-existe@reset.test"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Si el email está registrado", response.data["detail"])

    def test_flujo_completo_de_reset(self):
        self.client.post(reverse("auth-password-reset"), {"email": self.user.email})

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = token_generator.make_token(self.user)
        response = self.client.post(reverse("auth-password-reset-confirm"), {
            "uid": uid, "token": token, "new_password": "NuevaContrasena-456",
        })
        self.assertEqual(response.status_code, 200, response.data)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NuevaContrasena-456"))

    def test_token_invalido_falla(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        response = self.client.post(reverse("auth-password-reset-confirm"), {
            "uid": uid, "token": "token-trucho", "new_password": "NuevaContrasena-456",
        })
        self.assertEqual(response.status_code, 400)


class UsernameResetRequestTests(TestCase):
    """POST /api/auth/username-reset/ — recuperar el email (usuario) a
    partir del DNI. No devuelve el email en la respuesta (se lo manda por
    mail a la propia cuenta) para no permitir "pescar" qué email tiene un
    DNI dado."""

    def setUp(self):
        cache.clear()
        self.org = make_organization()
        self.user = make_user(self.org, groups=["operadores"], email="con-dni@org.test", dni="30111222")

    def test_dni_inexistente_devuelve_generico(self):
        response = self.client.post(reverse("auth-username-reset"), {"dni": "00000000"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Si el DNI está registrado", response.data["detail"])

    def test_dni_existente_manda_el_mail_y_no_expone_el_email_en_la_respuesta(self):
        from django.core import mail

        response = self.client.post(reverse("auth-username-reset"), {"dni": "30111222"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(self.user.email, str(response.data))

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertIn(self.user.email, mail.outbox[0].body)

    def test_token_no_sirve_dos_veces(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = token_generator.make_token(self.user)
        self.client.post(reverse("auth-password-reset-confirm"), {
            "uid": uid, "token": token, "new_password": "NuevaContrasena-456",
        })
        response = self.client.post(reverse("auth-password-reset-confirm"), {
            "uid": uid, "token": token, "new_password": "OtraContrasena-789",
        })
        self.assertEqual(response.status_code, 400)
