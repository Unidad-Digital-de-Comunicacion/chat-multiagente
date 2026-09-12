from django.core.management.base import BaseCommand
from django.utils import timezone

from business_hours.services import sincronizar_feriados


class Command(BaseCommand):
    help = "Sincroniza el catálogo compartido de feriados nacionales (organization=None) para un año."

    def add_arguments(self, parser):
        parser.add_argument("anio", type=int, nargs="?", default=timezone.localdate().year)

    def handle(self, *args, **options):
        anio = options["anio"]
        ok = sincronizar_feriados(anio)
        if ok:
            self.stdout.write(self.style.SUCCESS(f"Feriados de {anio} sincronizados."))
        else:
            self.stderr.write(self.style.ERROR(f"No se pudo sincronizar feriados de {anio} (ver logs)."))
