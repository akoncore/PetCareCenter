from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import RegisterView, LoginView, LogoutView, MeView, InvitationViewSet

router = DefaultRouter()
router.register("invitations", InvitationViewSet, basename="invitation")
urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
] + router.urls
