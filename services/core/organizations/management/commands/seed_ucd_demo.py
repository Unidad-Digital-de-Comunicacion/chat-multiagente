"""Datos de demo para probar los 5 grupos de permisos de punta a punta:
organización UCD, un usuario por cada uno de los primeros 3 grupos
(superusuarios/administradores/encargados_difusion), 5 agentes (operadores)
repartidos en 3 equipos, y un árbol de menú de 2 niveles (5-7 opciones por
nivel). Idempotente — correrlo de nuevo no duplica nada.

No crea un usuario de analistas_datos (no lo pidió la consigna) ni toca
otras organizaciones.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from business_hours.models import HorarioAtencion
from menu.models import MenuOpcion
from organizations.models import Organization
from teams.models import Team
from users.group_permissions import sync_groups
from users.models import User

PASSWORD_DEMO = "Contrasena-123"


def _get_or_create_user(email, organization, groups, grupos_por_nombre, **extra):
    user, created = User.objects.get_or_create(
        email=email, defaults={"organization": organization, **extra},
    )
    if created:
        user.set_password(PASSWORD_DEMO)
        user.save()
    elif extra:
        # `get_or_create` no toca `defaults` en un usuario que ya existía —
        # sincronizamos igual los flags que sí pasamos acá (is_staff/
        # is_superuser) para que correr el seed de nuevo repare una cuenta
        # de demo vieja que quedó desactualizada (ej. si se le sumó
        # `is_superuser=True` al superusuario en una versión más nueva del
        # comando), sin tocar nada que no se haya pasado por acá.
        for campo, valor in extra.items():
            setattr(user, campo, valor)
        user.save(update_fields=list(extra.keys()))
    user.groups.set([grupos_por_nombre[g] for g in groups])
    return user, created


class Command(BaseCommand):
    help = "Crea la organización de demo UCD: usuarios, equipos y un menú de 2 niveles."

    @transaction.atomic
    def handle(self, *args, **options):
        grupos = sync_groups()

        org, org_creada = Organization.objects.get_or_create(
            slug="ucd", defaults={"name": "UCD", "plan": Organization.Plan.PROFESIONAL},
        )
        self.stdout.write(self.style.SUCCESS(f"Organización UCD {'creada' if org_creada else 'ya existía'} (id={org.id})"))

        # --- Equipos (3) ---------------------------------------------------
        nombres_equipos = ["Soporte", "Ventas", "Postventa"]
        equipos = {}
        for nombre in nombres_equipos:
            equipo, _ = Team.objects.get_or_create(organization=org, name=nombre)
            equipos[nombre] = equipo
        self.stdout.write(self.style.SUCCESS(f"Equipos listos: {', '.join(nombres_equipos)}"))

        # --- Usuarios --------------------------------------------------------
        # Superusuario de plataforma: sin organización (gestiona TODAS las
        # organizaciones y sus admins desde /admin/ y desde la sección
        # "Plataforma" del Admin Panel), is_staff Y is_superuser de Django —
        # hace falta el flag real (no sólo el grupo) porque las vistas de
        # alcance global usan `is_superuser=True` + sin organización como
        # criterio para distinguir "toda la plataforma" de "mi organización"
        # (`common.permissions.IsPlatformSuperuser`, `UserManager.create_superuser`).
        superusuario, _ = _get_or_create_user(
            "superusuario@ucd.demo", None, ["superusuarios"], grupos, is_staff=True, is_superuser=True,
        )
        administrador, _ = _get_or_create_user(
            "admin@ucd.demo", org, ["administradores"], grupos,
        )
        encargado_difusion, _ = _get_or_create_user(
            "difusion@ucd.demo", org, ["encargados_difusion"], grupos,
        )

        agentes = []
        for i in range(1, 6):
            agente, _ = _get_or_create_user(f"agente{i}@ucd.demo", org, ["operadores"], grupos)
            agentes.append(agente)

        # Reparto de los 5 agentes en los 3 equipos (algunos en más de uno).
        equipos["Soporte"].members.set([agentes[0], agentes[1], agentes[4]])
        equipos["Ventas"].members.set([agentes[1], agentes[2]])
        equipos["Postventa"].members.set([agentes[3], agentes[4]])

        self.stdout.write(self.style.SUCCESS(
            "Usuarios listos: superusuario@ucd.demo, admin@ucd.demo, difusion@ucd.demo, "
            "agente1..5@ucd.demo (contraseña de todos: " + PASSWORD_DEMO + ")"
        ))

        # --- Horario semanal básico (lunes a viernes 9-18) -------------------
        if not HorarioAtencion.objects.filter(organization=org).exists():
            for dia in range(5):  # 0=lunes ... 4=viernes
                HorarioAtencion.objects.create(
                    organization=org, dia_semana=dia,
                    hora_inicio="09:00", hora_fin="18:00",
                )
            self.stdout.write(self.style.SUCCESS("Horario semanal lunes-viernes 09:00-18:00 cargado."))

        # --- Árbol de menú: 2 niveles, 5-7 opciones cada uno -----------------
        if MenuOpcion.objects.filter(organization=org).exists():
            self.stdout.write("El árbol de menú de UCD ya existe, no se recrea.")
            return

        def _opcion(texto, tipo, parent=None, **campos):
            return MenuOpcion.objects.create(
                organization=org, texto=texto, tipo=tipo, parent=parent, **campos,
            )

        ventas = _opcion("Ventas", MenuOpcion.Tipo.SUBMENU)
        for texto in ["Planes y Precios", "Promociones Vigentes", "Formas de Pago", "Estado de mi Pedido"]:
            _opcion(texto, MenuOpcion.Tipo.RESPUESTA, parent=ventas, respuesta_texto=f"Información sobre: {texto}.")
        _opcion("Hablar con Ventas", MenuOpcion.Tipo.DERIVACION, parent=ventas, team=equipos["Ventas"])
        _opcion("Volver al Menú Principal", MenuOpcion.Tipo.INICIO, parent=ventas)

        soporte = _opcion("Soporte Técnico", MenuOpcion.Tipo.SUBMENU)
        for texto in ["Problemas de Conexión", "Restablecer Contraseña", "Reportar una Falla", "Estado del Servicio"]:
            _opcion(texto, MenuOpcion.Tipo.RESPUESTA, parent=soporte, respuesta_texto=f"Información sobre: {texto}.")
        _opcion("Hablar con Soporte", MenuOpcion.Tipo.DERIVACION, parent=soporte, team=equipos["Soporte"])
        _opcion("Volver al Menú Principal", MenuOpcion.Tipo.INICIO, parent=soporte)

        faq = _opcion("Preguntas Frecuentes", MenuOpcion.Tipo.SUBMENU)
        preguntas = [
            "¿Cómo doy de baja el servicio?",
            "¿Cómo cambio mi plan?",
            "¿Tienen atención los fines de semana?",
            "¿Cómo actualizo mis datos?",
            "¿Dónde veo mis facturas?",
        ]
        for texto in preguntas:
            _opcion(texto, MenuOpcion.Tipo.RESPUESTA, parent=faq, respuesta_texto=f"Respuesta a: {texto}")
        _opcion("Volver al Menú Principal", MenuOpcion.Tipo.INICIO, parent=faq)

        _opcion(
            "Horarios de Atención", MenuOpcion.Tipo.RESPUESTA,
            respuesta_texto="Atendemos de lunes a viernes de 09:00 a 18:00hs.",
        )
        _opcion("Hablar con un Operador", MenuOpcion.Tipo.DERIVACION, team=equipos["Soporte"])
        _opcion("Finalizar", MenuOpcion.Tipo.TERMINAR)

        self.stdout.write(self.style.SUCCESS(
            "Árbol de menú de UCD creado: 6 opciones en la raíz "
            "(Ventas, Soporte Técnico, Preguntas Frecuentes, Horarios de Atención, "
            "Hablar con un Operador, Finalizar), 5-6 opciones por cada submenú."
        ))
