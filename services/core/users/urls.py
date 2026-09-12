from rest_framework.routers import DefaultRouter

from django.urls import include, path

from .views import MeView, UserViewSet

router = DefaultRouter()
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    path("users/me/", MeView.as_view(), name="user-me"),
    path("", include(router.urls)),
]
