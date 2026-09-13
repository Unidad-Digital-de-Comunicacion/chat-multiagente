"""Las 7 etiquetas de estado que pide la consigna, con un color default
razonable (el admin puede recolorearlas después). `asegurar_etiquetas_sistema`
es idempotente y se llama de forma lazy (en `EtiquetaViewSet.get_queryset`,
mismo patrón que `business_hours.services.sincronizar_feriados` para el
catálogo compartido) para que también se completen en organizaciones que ya
existían antes de esta app."""

ETIQUETAS_SISTEMA = [
    {"codigo": "pendiente", "nombre": "Pendiente", "color": "#9CA3AF"},
    {"codigo": "asignada", "nombre": "Asignada", "color": "#60A5FA"},
    {"codigo": "tomada", "nombre": "Tomada", "color": "#818CF8"},
    {"codigo": "en_proceso", "nombre": "En proceso", "color": "#F59E0B"},
    {"codigo": "en_pausa", "nombre": "En pausa", "color": "#FBBF24"},
    {"codigo": "rechazado", "nombre": "Rechazado", "color": "#EF4444"},
    {"codigo": "resuelto", "nombre": "Resuelto", "color": "#22C55E"},
]


def asegurar_etiquetas_sistema(organization_id):
    from .models import Etiqueta

    existentes = set(
        Etiqueta.objects.filter(organization_id=organization_id, es_sistema=True)
        .values_list("codigo", flat=True)
    )
    faltantes = [d for d in ETIQUETAS_SISTEMA if d["codigo"] not in existentes]
    if not faltantes:
        return
    Etiqueta.objects.bulk_create([
        Etiqueta(
            organization_id=organization_id,
            codigo=d["codigo"],
            nombre=d["nombre"],
            color=d["color"],
            es_sistema=True,
            orden=ETIQUETAS_SISTEMA.index(d),
        )
        for d in faltantes
    ])
