from django.urls import path

from .views import MyOrganizationView

urlpatterns = [
    path("organizations/me/", MyOrganizationView.as_view(), name="organization-me"),
]
