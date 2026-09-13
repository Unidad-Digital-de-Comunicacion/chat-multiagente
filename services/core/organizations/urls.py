from rest_framework.routers import DefaultRouter

from django.urls import include, path

from .views import MyOrganizationView, PlatformOrganizationViewSet

router = DefaultRouter()
router.register("plataforma/organizaciones", PlatformOrganizationViewSet, basename="plataforma-organizacion")

urlpatterns = [
    path("organizations/me/", MyOrganizationView.as_view(), name="organization-me"),
    path("", include(router.urls)),
]
