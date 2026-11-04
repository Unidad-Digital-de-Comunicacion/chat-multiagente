from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ChequeosSaludView, IncidenteViewSet, LogsView

router = DefaultRouter()
router.register("plataforma/incidentes", IncidenteViewSet, basename="plataforma-incidente")

urlpatterns = [
    path("plataforma/logs/", LogsView.as_view(), name="plataforma-logs"),
    path("plataforma/chequeos-salud/", ChequeosSaludView.as_view(), name="plataforma-chequeos-salud"),
    path("", include(router.urls)),
]
