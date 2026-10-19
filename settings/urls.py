from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from apps.core.health import live, ready

urlpatterns = [
    path("health/live/", live),
    path("health/ready/", ready),
    path("admin/", admin.site.urls),
    path("api/", include("apps.users.urls")),
    path("api/", include("apps.clinics.urls")),
    path("api/", include("apps.pets.urls")),
    path("api/", include("apps.booking.urls")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
