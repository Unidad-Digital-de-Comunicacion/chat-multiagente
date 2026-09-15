from rest_framework.routers import DefaultRouter

from django.urls import include, path

from .views import ConversacionViewSet, MensajeEntranteView

router = DefaultRouter()
router.register("conversaciones", ConversacionViewSet, basename="conversacion")

urlpatterns = [
    path("bot/mensaje-entrante/", MensajeEntranteView.as_view(), name="bot-mensaje-entrante"),
    path("", include(router.urls)),
]
