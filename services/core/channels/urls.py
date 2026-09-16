from rest_framework.routers import DefaultRouter

from django.urls import include, path

from .views import CanalViewSet, InternalCanalConfigView, InternalCanalPorOrganizacionView

router = DefaultRouter()
router.register("canales", CanalViewSet, basename="canal")

urlpatterns = [
    path("internal/canales/<uuid:canal_uuid>/", InternalCanalConfigView.as_view(), name="internal-canal-config"),
    path(
        "internal/canales/organizacion/<int:organization_id>/<str:tipo>/",
        InternalCanalPorOrganizacionView.as_view(), name="internal-canal-por-organizacion",
    ),
    path("", include(router.urls)),
]
