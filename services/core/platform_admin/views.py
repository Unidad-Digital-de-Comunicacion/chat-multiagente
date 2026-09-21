import secrets
from pathlib import Path

from django.http import FileResponse, Http404
from django.utils import timezone
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework import generics, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from channels.models import Canal
from common.permissions import IsPlatformSuperuser
from conversations.models import Conversacion
from conversations.serializers import ConversacionHistorialSerializer
from conversations.views import PREFETCH_HISTORIAL, anotar_ultima_actividad, aplicar_filtros_historial
from organizations.models import Organization
from teams.models import Team
from users.models import User

from .defaults import asegurar_service_tokens
from .models import MetaAppConfig, ServiceToken
from .serializers import MetaAppConfigSerializer, ServiceTokenSerializer
from .service_auth import IsChannelGatewayService, ServiceTokenAuthentication

MANUAL_PDF_PATH = Path(__file__).resolve().parent / "manual" / "manual-admin-panel.pdf"


class ServiceTokenViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet,
):
    """Tokens para que los OTROS microservicios del proyecto se autentiquen
    contra Core — ver el docstring de `platform_admin.models.ServiceToken`.
    Sin alta/baja: son siempre los 5 servicios de la sección 3 de
    docs/CONTEXTO_PROYECTO.md, autogenerados (`asegurar_service_tokens`)."""

    queryset = ServiceToken.objects.all()
    serializer_class = ServiceTokenSerializer
    permission_classes = [IsPlatformSuperuser]

    def get_queryset(self):
        asegurar_service_tokens()
        return super().get_queryset()

    @action(detail=True, methods=["post"])
    def generar(self, request, pk=None):
        """Genera un token seguro al azar y lo devuelve en texto plano UNA
        vez en esta respuesta — a partir de acá sólo se ve enmascarado
        (`token_preview`), aunque a diferencia de `users.UserViewSet.
        reset_password` el valor real SÍ queda guardado (cifrado, ver
        `ServiceToken.token`): Core necesita poder reenviarlo tal cual
        hacia ese microservicio en la dirección inversa."""
        service_token = self.get_object()
        nuevo = secrets.token_urlsafe(32)
        service_token.token = nuevo
        service_token.generado_at = timezone.now()
        service_token.save(update_fields=["token", "generado_at", "updated_at"])
        return Response({"token": nuevo, **self.get_serializer(service_token).data})


class MetaAppConfigView(APIView):
    """Singleton editable desde Plataforma — ver el docstring de
    `platform_admin.models.MetaAppConfig`. GET siempre existe (`obtener()`
    la crea vacía la primera vez); PATCH permite cargar/reemplazar `app_id`/
    `app_secret` sin tocar el servidor a mano. Consumida por Channel
    Gateway vía `InternalMetaAppConfigView`, no por acá (esto es sólo para
    el Admin Panel, con el JWT del superusuario)."""

    permission_classes = [IsPlatformSuperuser]

    def get(self, request):
        return Response(MetaAppConfigSerializer(MetaAppConfig.obtener()).data)

    def patch(self, request):
        config = MetaAppConfig.obtener()
        serializer = MetaAppConfigSerializer(config, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(MetaAppConfigSerializer(config).data)


class InternalMetaAppConfigView(APIView):
    """Único lugar donde `app_secret` sale de Core en texto plano — sólo lo
    puede llamar Channel Gateway (mismo criterio que `channels.views.
    InternalCanalConfigView`), nunca con el JWT de un usuario humano. Se
    pide de nuevo en cada webhook entrante (sin cachear del lado de Channel
    Gateway) para que un cambio hecho en Plataforma tenga efecto inmediato,
    sin reiniciar ningún contenedor — mismo criterio que ya usa `Canal.
    api_key`/`webhook_secret`."""

    authentication_classes = [ServiceTokenAuthentication]
    permission_classes = [IsChannelGatewayService]

    def get(self, request):
        config = MetaAppConfig.obtener()
        return Response({"app_id": config.app_id, "app_secret": config.app_secret})


class PlatformStatsView(APIView):
    """Estadísticas de uso generales de este microservicio (Core) — sección
    "Estadísticas" del Admin Panel, sólo superusuario real. No hay
    conversaciones que contar todavía (Conversation Engine, Fase 4): son
    los conteos de lo que Core sí gestiona hoy."""

    permission_classes = [IsPlatformSuperuser]

    def get(self, request):
        organizaciones = Organization.objects.all()
        por_organizacion = [
            {
                "organization_id": org.id,
                "organization_name": org.name,
                "is_active": org.is_active,
                "usuarios": org.users.count(),
                "user_limit": org.user_limit,
                "equipos": org.teams.count(),
                "canales_activos": org.canales.filter(activo=True).count(),
            }
            for org in organizaciones.order_by("name")
        ]
        data = {
            "organizaciones_total": organizaciones.count(),
            "organizaciones_activas": organizaciones.filter(is_active=True).count(),
            "usuarios_total": User.objects.count(),
            "usuarios_activos": User.objects.filter(is_active=True).count(),
            "equipos_total": Team.objects.count(),
            "canales_configurados": Canal.objects.exclude(api_key="").count(),
            "canales_activos": Canal.objects.filter(activo=True).count(),
            "por_organizacion": por_organizacion,
        }
        return Response(data)


class ExternalApiHealthView(APIView):
    """Salud general de las APIs EXTERNAS (WhatsApp/Messenger/Instagram vía
    la Graph API de Meta, Webchat que todavía no tiene servidor propio) de
    TODAS las organizaciones a la vez — a diferencia de `channels.
    CanalViewSet` (que un Admin usa para configurar/verificar los 4 canales
    de su propia organización), esto es de sólo lectura: el superusuario
    ve el último resultado guardado, no dispara un chequeo nuevo desde
    acá — eso sigue siendo una acción de configuración de cada organización."""

    permission_classes = [IsPlatformSuperuser]

    def get(self, request):
        canales = Canal.objects.select_related("organization").order_by("organization__name", "tipo")
        data = [
            {
                "organization_id": canal.organization_id,
                "organization_name": canal.organization.name,
                "tipo": canal.tipo,
                "tipo_display": canal.get_tipo_display(),
                "activo": canal.activo,
                "api_key_configurada": bool(canal.api_key),
                "ultimo_chequeo_at": canal.ultimo_chequeo_at,
                "ultimo_chequeo_ok": canal.ultimo_chequeo_ok,
                "ultimo_chequeo_detalle": canal.ultimo_chequeo_detalle,
            }
            for canal in canales
        ]
        return Response(data)


class HistorialConversacionesPlatformView(generics.ListAPIView):
    """Historial resumido (inicio/derivación/fin — `ConversacionHistorial
    Serializer`, ver su docstring) de las conversaciones de TODAS las
    organizaciones a la vez — a diferencia de `conversations.views.
    ConversacionViewSet.historial` (una sola organización, para
    `administradores`), esto es sólo del superusuario real. Paginado
    (a diferencia de `ExternalApiHealthView` de acá arriba, que sí
    devuelve todo sin paginar — ahí el total está acotado a 4 canales por
    organización, acá el volumen de conversaciones no tiene techo).
    Ordenado por organización (para que el Admin Panel lo agrupe
    visualmente sin pedidos aparte por cada una) y, dentro de cada una, por
    `ultima_actividad` descendente — ver `conversations.views.
    anotar_ultima_actividad`."""

    serializer_class = ConversacionHistorialSerializer
    permission_classes = [IsPlatformSuperuser]

    def get_queryset(self):
        queryset = Conversacion.objects.select_related(
            "contact", "operador", "team", "organization",
        ).prefetch_related(*PREFETCH_HISTORIAL)
        queryset = anotar_ultima_actividad(queryset)
        queryset = aplicar_filtros_historial(queryset, self.request)
        return queryset.order_by("organization__name", "-ultima_actividad")


class ManualDownloadView(APIView):
    """Descarga del manual de uso del Admin Panel (PDF con capturas de
    pantalla de la configuración del core) — sólo superusuario real."""

    permission_classes = [IsPlatformSuperuser]

    def get(self, request):
        if not MANUAL_PDF_PATH.exists():
            raise Http404("El manual todavía no está disponible.")
        return FileResponse(
            open(MANUAL_PDF_PATH, "rb"), as_attachment=True, filename="manual-admin-panel.pdf",
            content_type="application/pdf",
        )


# Documentos en Markdown para pasarle a otro equipo/agente sin necesitar
# acceso al repo (ej. el dev que arma la app Android contra este mismo
# backend) — a diferencia de MANUAL_PDF_PATH (que vive DENTRO de
# services/core), la fuente de estos sigue siendo docs/ y
# UDCOperadorAPP/AGENTS.md en la raíz del repo: docker-compose.yml monta
# esos dos paths de sólo lectura adentro del contenedor de Core (servicio
# `core`, ver sus `volumes`) en vez de duplicar el contenido acá — así no
# hay que recordar copiarlos cada vez que se actualiza la documentación.
DOCUMENTOS_TECNICOS = {
    "operators-desk-api": {
        "path": Path("/docs_repo/operators-desk-api-contract.md"),
        "filename": "operators-desk-api-contract.md",
    },
    "operators-desk-agente-android": {
        "path": Path("/agents_android.md"),
        "filename": "AGENTS-android.md",
    },
}


class DocumentoTecnicoView(APIView):
    """Mismo gate que `ManualDownloadView` (sólo superusuario real) — ver
    `DOCUMENTOS_TECNICOS` acá arriba para qué `slug` existen."""

    permission_classes = [IsPlatformSuperuser]

    def get(self, request, slug):
        documento = DOCUMENTOS_TECNICOS.get(slug)
        if documento is None:
            raise Http404("No existe ese documento.")
        if not documento["path"].exists():
            raise Http404("Ese documento todavía no está disponible en este ambiente.")
        return FileResponse(
            open(documento["path"], "rb"), as_attachment=True, filename=documento["filename"],
            content_type="text/markdown; charset=utf-8",
        )


class PlatformSchemaView(SpectacularAPIView):
    """El esquema OpenAPI (paths, params — nunca datos, sólo la FORMA de la
    API) — a propósito público (`AllowAny`), no detrás de
    `IsPlatformSuperuser` como el resto de "Plataforma". Motivo: Swagger UI/
    Redoc lo piden con un `fetch()` propio del navegador apenas cargan la
    página, SIN el header `Authorization` (no hay forma de que el JS de
    esos visores sepa del JWT que Core usa — vive en el `localStorage` del
    Admin Panel, otro origen) — si este endpoint exige auth, ese primer
    fetch da 401 y el visor nunca llega a levantar ("Failed to load API
    definition"/"Something went wrong", pegar el token en el botón
    "Authorize" no ayuda porque ESE fetch inicial ya falló, antes de
    mostrar ningún botón). Lo único que se expone acá es la forma de la
    API (nombres de endpoints/parámetros/campos) — nunca datos reales, esos
    siguen exigiendo autenticación real en cada endpoint de verdad. El
    link a este visor sigue sin aparecer en el menú de nadie más que el
    superusuario (`Layout.tsx`); esto sólo evita que quien conozca la URL
    de memoria y no tenga sesión se quede con una pantalla rota en vez de
    con la documentación."""

    permission_classes = [AllowAny]


class PlatformSwaggerView(SpectacularSwaggerView):
    pass


class PlatformRedocView(SpectacularRedocView):
    pass
