"""Portado tal cual de `chatbot/feriados_client.py` (no agrega tecnología
nueva: es sólo un cliente HTTP contra una API pública)."""
import requests

URL = "https://api.argentinadatos.com/v1/feriados/{anio}"
TIMEOUT = 5


def obtener_feriados(anio):
    """Lista de {'fecha': 'YYYY-MM-DD', 'tipo': ..., 'nombre': ...} para ese año."""
    r = requests.get(URL.format(anio=anio), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()
