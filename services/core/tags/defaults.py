"""Las 7 etiquetas de estado que pide la consigna, con un color default
razonable (el admin puede recolorearlas después), más la sincronización
"cada equipo es una etiqueta". Ambas funciones son idempotentes y se llaman
de forma lazy (en `EtiquetaViewSet.get_queryset`, mismo patrón que
`business_hours.services.sincronizar_feriados` para el catálogo compartido)
para que también se completen en organizaciones/equipos que ya existían
antes de esta app o de que se cargara un equipo nuevo."""

ETIQUETAS_SISTEMA = [
    {"codigo": "pendiente", "nombre": "Pendiente", "color": "#9CA3AF"},
    {"codigo": "asignada", "nombre": "Asignada", "color": "#60A5FA"},
    {"codigo": "tomada", "nombre": "Tomada", "color": "#818CF8"},
    {"codigo": "en_proceso", "nombre": "En proceso", "color": "#F59E0B"},
    {"codigo": "en_pausa", "nombre": "En pausa", "color": "#FBBF24"},
    {"codigo": "rechazado", "nombre": "Rechazado", "color": "#EF4444"},
    {"codigo": "resuelto", "nombre": "Resuelto", "color": "#22C55E"},
]

COLOR_EQUIPO_DEFAULT = "#3454D1"


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


def asegurar_etiquetas_equipo(organization_id):
    """"Cada equipo es una etiqueta": una por `Team`, autogenerada y con el
    nombre siempre igual al del equipo (si lo renombran, se corrige acá) —
    no se crea/borra/renombra a mano desde la API de etiquetas."""
    from teams.models import Team

    from .models import Etiqueta

    equipos = Team.objects.filter(organization_id=organization_id)
    existentes = {e.team_id: e for e in Etiqueta.objects.filter(organization_id=organization_id, team__isnull=False)}

    nuevas = [
        Etiqueta(organization_id=organization_id, team_id=equipo.id, nombre=equipo.name, color=COLOR_EQUIPO_DEFAULT)
        for equipo in equipos
        if equipo.id not in existentes
    ]
    if nuevas:
        Etiqueta.objects.bulk_create(nuevas)

    for equipo in equipos:
        etiqueta = existentes.get(equipo.id)
        if etiqueta is not None and etiqueta.nombre != equipo.name:
            etiqueta.nombre = equipo.name
            etiqueta.save(update_fields=["nombre"])
