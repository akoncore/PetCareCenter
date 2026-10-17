from rest_framework.routers import DefaultRouter
from .views import ServiceViewSet, AppointmentViewSet, TransportViewSet

router = DefaultRouter()
router.register("services", ServiceViewSet, basename="service")
router.register("appointments", AppointmentViewSet, basename="appointment")
router.register("transport", TransportViewSet, basename="transport")
urlpatterns = router.urls
