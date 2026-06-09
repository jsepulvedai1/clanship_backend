from django.urls import path
from chat.consumers import ChatConsumer
from jobs.consumers import JobConsumer

websocket_urlpatterns = [
    path("ws/chat/<int:room_id>/", ChatConsumer.as_asgi()),
    path("ws/jobs/", JobConsumer.as_asgi()),
]
