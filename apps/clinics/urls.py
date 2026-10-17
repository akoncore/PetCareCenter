from rest_framework.routers import DefaultRouter
from .views import ClinicViewSet, ClinicMembershipViewSet

router = DefaultRouter()
router.register("clinics", ClinicViewSet, basename="clinic")
router.register("memberships", ClinicMembershipViewSet, basename="membership")
urlpatterns = router.urls
