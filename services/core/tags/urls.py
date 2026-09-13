from rest_framework.routers import DefaultRouter

from django.urls import include, path

from .views import EtiquetaViewSet

router = DefaultRouter()
router.register("etiquetas", EtiquetaViewSet, basename="etiqueta")

urlpatterns = [
    path("", include(router.urls)),
]
