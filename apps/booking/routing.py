from django.urls import path

from .consumers import BookingConsumer

websocket_urlpatterns = [
    path("ws/appointments/<int:pk>/", BookingConsumer.as_asgi(), {"resource": "appointment"}),
    path("ws/transport/<int:pk>/", BookingConsumer.as_asgi(), {"resource": "transport"}),
]
