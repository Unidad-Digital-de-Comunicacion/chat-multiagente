from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    JWKSView, LoginView, PasswordResetConfirmView, PasswordResetRequestView, UsernameResetRequestView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("jwks/", JWKSView.as_view(), name="auth-jwks"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("password-reset-confirm/", PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
    path("username-reset/", UsernameResetRequestView.as_view(), name="auth-username-reset"),
]
