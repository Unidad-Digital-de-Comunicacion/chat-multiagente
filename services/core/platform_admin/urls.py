from rest_framework.routers import DefaultRouter

from django.urls import include, path

from .views import (
    DocumentoTecnicoView, ExternalApiHealthView, HistorialConversacionesPlatformView, ManualDownloadView,
    PlatformRedocView, PlatformSchemaView, PlatformStatsView, PlatformSwaggerView, ServiceTokenViewSet,
)

router = DefaultRouter()
router.register("plataforma/tokens-servicios", ServiceTokenViewSet, basename="plataforma-token-servicio")

urlpatterns = [
    path("plataforma/estadisticas/", PlatformStatsView.as_view(), name="plataforma-estadisticas"),
    path("plataforma/salud-canales/", ExternalApiHealthView.as_view(), name="plataforma-salud-canales"),
    path(
        "plataforma/historial-conversaciones/", HistorialConversacionesPlatformView.as_view(),
        name="plataforma-historial-conversaciones",
    ),
    path("plataforma/manual/", ManualDownloadView.as_view(), name="plataforma-manual"),
    path("plataforma/manual/<slug:slug>/", DocumentoTecnicoView.as_view(), name="plataforma-manual-documento"),
    path("plataforma/schema/", PlatformSchemaView.as_view(), name="plataforma-schema"),
    path("plataforma/schema/swagger/", PlatformSwaggerView.as_view(url_name="plataforma-schema"), name="plataforma-swagger"),
    path("plataforma/schema/redoc/", PlatformRedocView.as_view(url_name="plataforma-schema"), name="plataforma-redoc"),
    path("", include(router.urls)),
]
