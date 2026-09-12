from rest_framework.routers import DefaultRouter

from django.urls import include, path

from .views import TeamViewSet

router = DefaultRouter()
router.register("teams", TeamViewSet, basename="team")

urlpatterns = [
    path("", include(router.urls)),
]
