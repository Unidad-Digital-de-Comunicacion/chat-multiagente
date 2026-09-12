from rest_framework.routers import DefaultRouter

from django.urls import include, path

from .views import MenuOpcionViewSet

router = DefaultRouter()
router.register("menu-opciones", MenuOpcionViewSet, basename="menu-opcion")

urlpatterns = [
    path("", include(router.urls)),
]
