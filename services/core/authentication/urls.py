from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import JWKSView, LoginView

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("jwks/", JWKSView.as_view(), name="auth-jwks"),
]
