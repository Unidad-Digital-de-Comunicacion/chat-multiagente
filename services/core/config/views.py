"""Contenido legal estático, servido por Core mismo (no amerita su propia
app Django) — público a propósito (sin auth), Meta lo exige como campo
obligatorio ("Privacy Policy URL") al configurar el webhook de Messenger/
Instagram, y cualquier contacto real tiene que poder abrirlo sin sesión."""
from django.shortcuts import render


def privacy_policy(request):
    return render(request, "legal/privacy_policy.html")
