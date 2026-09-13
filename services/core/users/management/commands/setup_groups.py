from django.core.management.base import BaseCommand

from users.group_permissions import sync_groups


class Command(BaseCommand):
    help = "Crea/actualiza los 5 grupos de permisos de la plataforma (idempotente). Correr después de cada migrate."

    def handle(self, *args, **options):
        grupos = sync_groups()
        for nombre, grupo in grupos.items():
            self.stdout.write(self.style.SUCCESS(f"Grupo listo: {nombre} ({grupo.permissions.count()} permisos)"))
