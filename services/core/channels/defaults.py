"""Los 4 canales que pide la consigna (WhatsApp, Messenger, Instagram,
Webchat — mismo listado que la sección 3 de docs/CONTEXTO_PROYECTO.md) se
autogeneran por organización la primera vez que se lista el catálogo, sin
api key y desactivados — mismo patrón lazy que `tags.defaults.
asegurar_etiquetas_sistema`."""


def asegurar_canales(organization_id):
    from .models import Canal

    existentes = set(
        Canal.objects.filter(organization_id=organization_id).values_list("tipo", flat=True)
    )
    faltantes = [tipo for tipo, _ in Canal.Tipo.choices if tipo not in existentes]
    if not faltantes:
        return
    Canal.objects.bulk_create([
        Canal(organization_id=organization_id, tipo=tipo) for tipo in faltantes
    ])
