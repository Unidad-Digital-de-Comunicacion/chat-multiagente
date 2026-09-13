"""Un `ServiceToken` por cada microservicio del proyecto (sección 3 de
docs/CONTEXTO_PROYECTO.md) se autogenera la primera vez que se lista el
catálogo, sin token y desactivado — mismo patrón lazy que
`channels.defaults.asegurar_canales`."""


def asegurar_service_tokens():
    from .models import ServiceToken

    existentes = set(ServiceToken.objects.values_list("servicio", flat=True))
    faltantes = [servicio for servicio, _ in ServiceToken.Servicio.choices if servicio not in existentes]
    if not faltantes:
        return
    ServiceToken.objects.bulk_create([ServiceToken(servicio=servicio) for servicio in faltantes])
