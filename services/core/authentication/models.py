from django.db import models
from django.utils import timezone


class LoginLockout(models.Model):
    """Control de fuerza bruta sobre `/api/auth/login/`, por IP (no por
    cuenta): a las 3 fallas seguidas, esa IP queda bloqueada 12 horas. No
    depende de ninguna organización — una IP puede intentar loguearse contra
    cuentas de cualquier organización — por eso se gestiona desde /admin/
    (grupo `superusuarios`), no desde el Admin Panel de una organización
    puntual."""

    ip_address = models.GenericIPAddressField(unique=True)
    failed_attempts = models.PositiveIntegerField(default=0)
    blocked_until = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(auto_now=True)

    @property
    def is_blocked(self):
        return bool(self.blocked_until and self.blocked_until > timezone.now())

    def registrar_fallo(self, *, max_intentos, horas_bloqueo):
        self.failed_attempts += 1
        if self.failed_attempts >= max_intentos:
            self.blocked_until = timezone.now() + timezone.timedelta(hours=horas_bloqueo)
        self.save(update_fields=["failed_attempts", "blocked_until", "last_attempt_at"])

    def registrar_exito(self):
        if self.failed_attempts or self.blocked_until:
            self.failed_attempts = 0
            self.blocked_until = None
            self.save(update_fields=["failed_attempts", "blocked_until", "last_attempt_at"])

    def __str__(self):
        return f"{self.ip_address} ({'bloqueada' if self.is_blocked else 'libre'})"

    class Meta:
        verbose_name = "Bloqueo de login por IP"
        verbose_name_plural = "Bloqueos de login por IP"
        ordering = ["-last_attempt_at"]
