from rest_framework.routers import DefaultRouter

from django.urls import include, path

from .views import ChangeMyPasswordView, GroupListView, MeView, PlatformUserViewSet, UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("plataforma/usuarios", PlatformUserViewSet, basename="plataforma-usuario")

urlpatterns = [
    path("users/me/", MeView.as_view(), name="user-me"),
    path("users/me/cambiar-password/", ChangeMyPasswordView.as_view(), name="user-me-change-password"),
    path("groups/", GroupListView.as_view(), name="group-list"),
    path("", include(router.urls)),
]
