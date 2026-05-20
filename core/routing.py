from django.urls import path
from core.consumers import MyGraphqlWsConsumer

websocket_urlpatterns = [
    path("graphql/", MyGraphqlWsConsumer.as_asgi()),
]
