from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health(_request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health", health),
    path("admin/", admin.site.urls),
    path("api/auth/", include("authentication.urls")),
    path("api/core/", include("organizations.urls")),
    path("api/core/", include("users.urls")),
    path("api/core/", include("teams.urls")),
    path("api/core/", include("business_hours.urls")),
    path("api/core/", include("menu.urls")),
]
