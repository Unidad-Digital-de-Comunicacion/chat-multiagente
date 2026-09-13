"""Textos por defecto de los mensajes del bot. Adaptado de
`chatbot/defaults.py` del repo garzamorada/chatbot: centraliza acá los
valores que se usan cuando el campo de `BotMessages` quedó vacío, para que
el panel de administración y (más adelante) el runtime del bot (Fase 3) usen
exactamente los mismos textos.
"""

MENSAJE_BIENVENIDA = (
    "¡Hola! Te está respondiendo el asistente virtual. "
    "Te ayudo con las consultas más frecuentes a través de este menú."
)
SALUDO_INICIAL = "Usted está en el menú principal, por favor seleccione la opción deseada."
SALUDO_AREA = 'Usted está en el área de "{area}", por favor seleccione la opción deseada.'
MENSAJE_DESPEDIDA = "Gracias por contactarnos. ¡Hasta luego!"
DERIVACION_TEXTO = "Hablar con un operador"
DERIVACION_MENSAJE = "Te derivamos con un operador. En breve te van a contactar. 🕑"
MENSAJE_CIERRE_INACTIVIDAD = (
    "Cerramos esta conversación por inactividad. Si necesitás algo más, "
    "volvé a escribirnos y con gusto te ayudamos. ¡Hasta pronto!"
)

# Variables disponibles dentro de cada plantilla, para mostrar como ayuda en
# el formulario del panel.
#   {area}   -> nombre del menú donde está el contacto (sólo saludo de área)
#   {nombre} -> nombre del contacto (vacío si no se tiene)
VARIABLES_POR_CAMPO = {
    "mensaje_bienvenida": ["nombre"],
    "saludo_inicial": ["nombre"],
    "saludo_area": ["area", "nombre"],
    "mensaje_despedida": ["nombre"],
    "mensaje_cierre_inactividad": ["nombre"],
    "derivacion_mensaje": ["area", "nombre"],
}

DEFAULT_POR_CAMPO = {
    "mensaje_bienvenida": MENSAJE_BIENVENIDA,
    "saludo_inicial": SALUDO_INICIAL,
    "saludo_area": SALUDO_AREA,
    "mensaje_despedida": MENSAJE_DESPEDIDA,
    "mensaje_cierre_inactividad": MENSAJE_CIERRE_INACTIVIDAD,
    "derivacion_texto": DERIVACION_TEXTO,
    "derivacion_mensaje": DERIVACION_MENSAJE,
}


def aplicar_variables(texto, area="", nombre=""):
    return (texto or "").replace("{area}", area or "").replace("{nombre}", nombre or "")
