from rest_framework.routers import DefaultRouter

from django.urls import include, path

from .views import CanalViewSet

router = DefaultRouter()
router.register("canales", CanalViewSet, basename="canal")

urlpatterns = [
    path("", include(router.urls)),
]
