from rest_framework.routers import DefaultRouter

from django.urls import include, path

from .views import DiaExcepcionalViewSet, HorarioAtencionViewSet, TeamHorarioHabilView

router = DefaultRouter()
router.register("horarios-atencion", HorarioAtencionViewSet, basename="horario-atencion")
router.register("dias-excepcionales", DiaExcepcionalViewSet, basename="dia-excepcional")

urlpatterns = [
    path("teams/<int:team_id>/horario-habil/", TeamHorarioHabilView.as_view(), name="team-horario-habil"),
    path("", include(router.urls)),
]
