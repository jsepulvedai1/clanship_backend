import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
import graphql_jwt

User = get_user_model()

class JobConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Validar Token JWT desde la query string
        query_string = self.scope['query_string'].decode('utf-8')
        token = None
        
        # Extraer token=XXXXX de la URL
        for param in query_string.split('&'):
            if param.startswith('token='):
                token = param.split('=')[1]
                break
                
        user = await self.get_user_from_token(token)
        
        if user is None or user.is_anonymous:
            # Rechazar conexión si no hay usuario válido
            await self.close(code=4003)
            return

        self.user = user
        self.user_group_name = f'user_{self.user.id}'

        # Unirse al grupo específico de este usuario
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Salir del grupo
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )

    async def job_notification(self, event):
        # Enviar la notificación completa al cliente (excluyendo la clave interna 'type')
        payload = {k: v for k, v in event.items() if k != 'type'}
        if 'job_id' in payload and payload['job_id'] is not None:
            payload['job_id'] = str(payload['job_id'])
        await self.send(text_data=json.dumps(payload))

    @database_sync_to_async
    def get_user_from_token(self, token):
        if not token:
            return None
        try:
            valid_data = graphql_jwt.utils.jwt_decode(token)
            user_model = get_user_model()
            user = user_model.objects.get(username=valid_data['username'])
            return user
        except Exception:
            return None
