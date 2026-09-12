"""Genera el par de claves RSA de firma de JWT si todavía no existen.

Uso local sin Docker (dev): correrlo a mano una vez.
Dentro de Docker: lo corre `entrypoint.sh` en cada arranque del contenedor
(es idempotente — si las claves ya están en el volumen `jwt_keys`, no hace
nada), así el par persiste entre reinicios del contenedor `core`.
"""
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Genera keys/jwt_private.pem y keys/jwt_public.pem (RS256) si no existen."

    def handle(self, *args, **options):
        private_path = Path(settings.JWT_PRIVATE_KEY_PATH)
        public_path = Path(settings.JWT_PUBLIC_KEY_PATH)

        if private_path.exists() and public_path.exists():
            self.stdout.write("generate_jwt_keys: ya existen, no se regeneran.")
            return

        private_path.parent.mkdir(parents=True, exist_ok=True)
        public_path.parent.mkdir(parents=True, exist_ok=True)

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        private_path.write_bytes(private_pem)
        private_path.chmod(0o600)
        public_path.write_bytes(public_pem)

        self.stdout.write(self.style.SUCCESS(f"generate_jwt_keys: par generado en {private_path.parent}"))
