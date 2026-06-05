import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from channels.db import database_sync_to_async
from .models import ChatRoom, Message
import graphql_jwt

User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'

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

        # Verificar si la sala existe y si el usuario tiene acceso
        has_access = await self.check_room_access(self.room_id, self.user)
        if not has_access:
            await self.close(code=4003)
            return

        # Unirse al grupo
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Salir del grupo
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    # Recibir mensaje del WebSocket (Frontend -> Backend)
    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message_text = text_data_json.get('message', '')
        action = text_data_json.get('action', '')

        if action == 'create_job':
            job_created = await self.create_job_if_not_exists(self.room_id)
            if job_created:
                sys_msg = await self.save_message(self.room_id, self.user, "El cliente ha solicitado iniciar un trabajo.")
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': sys_msg.text,
                        'sender_id': self.user.id,
                        'sender_username': self.user.username,
                        'created_at': sys_msg.created_at.isoformat(),
                        'system': True
                    }
                )

        if message_text:
            # Guardar el mensaje en DB
            message = await self.save_message(self.room_id, self.user, message_text)

            # Enviar mensaje al grupo de la sala
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message.text,
                    'sender_id': self.user.id,
                    'sender_username': self.user.username,
                    'created_at': message.created_at.isoformat()
                }
            )

    # Recibir mensaje del grupo (Backend -> Frontend)
    async def chat_message(self, event):
        # Enviar el mensaje al WebSocket en formato JSON
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender_id': event['sender_id'],
            'sender_username': event['sender_username'],
            'created_at': event['created_at'],
            'system': event.get('system', False)
        }))

    @database_sync_to_async
    def get_user_from_token(self, token):
        if not token:
            return None
        try:
            # Verificar y decodificar el token usando graphql_jwt
            valid_data = graphql_jwt.utils.jwt_decode(token)
            user_model = get_user_model()
            user = user_model.objects.get(username=valid_data['username'])
            return user
        except Exception:
            return None

    @database_sync_to_async
    def check_room_access(self, room_id, user):
        try:
            room = ChatRoom.objects.get(id=room_id)
            if room.customer == user or room.professional == user:
                return True
            return False
        except ChatRoom.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, room_id, user, text):
        room = ChatRoom.objects.get(id=room_id)
        return Message.objects.create(room=room, sender=user, text=text)

    @database_sync_to_async
    def create_job_if_not_exists(self, room_id):
        from jobs.models import Job
        room = ChatRoom.objects.get(id=room_id)
        active_job_exists = Job.objects.filter(
            customer=room.customer,
            professional=room.professional,
            status__in=[Job.Status.REQUESTED, Job.Status.AGREED, Job.Status.IN_VISIT]
        ).exists()

        if not active_job_exists:
            Job.objects.create(
                customer=room.customer,
                professional=room.professional,
                status=Job.Status.REQUESTED
            )
            return True
        return False
