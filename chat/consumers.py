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
        file_base64 = text_data_json.get('file_base64', None)
        file_name = text_data_json.get('file_name', None)
        message_type = text_data_json.get('message_type', 'TEXT')
        action = text_data_json.get('action', '')

        if action == 'create_job':
            job_created = await self.create_job_if_not_exists(self.room_id)
            if job_created:
                sys_msg = await self.save_message(self.room_id, self.user, "El cliente ha solicitado iniciar un trabajo.")
                avatar_url = await self.get_user_avatar_url(self.user)
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': sys_msg.text,
                        'sender_id': self.user.id,
                        'sender_username': self.user.username,
                        'sender_avatar_url': avatar_url,
                        'created_at': sys_msg.created_at.isoformat(),
                        'system': True
                    }
                )

        if message_text or (file_base64 and file_name):
            # Guardar el mensaje en DB
            message = await self.save_message_with_file_async(
                self.room_id, 
                self.user, 
                message_text, 
                file_base64, 
                file_name, 
                message_type
            )
            avatar_url = await self.get_user_avatar_url(self.user)
            file_url = await self.get_message_file_url(message)

            # Enviar mensaje al grupo de la sala
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message.text,
                    'sender_id': self.user.id,
                    'sender_username': self.user.username,
                    'sender_avatar_url': avatar_url,
                    'created_at': message.created_at.isoformat(),
                    'file_url': file_url,
                    'message_type': message.message_type
                }
            )

    # Recibir mensaje del grupo (Backend -> Frontend)
    async def chat_message(self, event):
        # Enviar el mensaje al WebSocket en formato JSON
        await self.send(text_data=json.dumps({
            'message': event.get('message', ''),
            'sender_id': event['sender_id'],
            'sender_username': event['sender_username'],
            'sender_avatar_url': event.get('sender_avatar_url'),
            'created_at': event['created_at'],
            'system': event.get('system', False),
            'file_url': event.get('file_url'),
            'message_type': event.get('message_type', 'TEXT')
        }))

    @database_sync_to_async
    def get_user_avatar_url(self, user):
        if not user.avatar:
            return None
        host = None
        for key, value in self.scope.get('headers', []):
            if key == b'host':
                host = value.decode('utf-8')
                break
        
        if not host:
            host = "localhost:8000"
            
        proto = 'http'
        for key, value in self.scope.get('headers', []):
            if key == b'x-forwarded-proto':
                proto = value.decode('utf-8')
                break
                
        if self.scope.get('scheme') == 'wss':
            proto = 'https'
            
        return f"{proto}://{host}{user.avatar.url}"

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
    def save_message_with_file_async(self, room_id, user, text, file_base64, file_name, message_type):
        import base64
        from django.core.files.base import ContentFile
        room = ChatRoom.objects.get(id=room_id)
        msg = Message(room=room, sender=user, text=text, message_type=message_type)
        if file_base64 and file_name:
            format, imgstr = file_base64.split(';base64,') if ';base64,' in file_base64 else (None, file_base64)
            data = ContentFile(base64.b64decode(imgstr), name=file_name)
            msg.file.save(file_name, data, save=False)
        msg.save()
        return msg

    @database_sync_to_async
    def get_message_file_url(self, message):
        if not message.file:
            return None
        host = None
        for key, value in self.scope.get('headers', []):
            if key == b'host':
                host = value.decode('utf-8')
                break
        
        if not host:
            host = "localhost:8000"
            
        proto = 'http'
        for key, value in self.scope.get('headers', []):
            if key == b'x-forwarded-proto':
                proto = value.decode('utf-8')
                break
                
        if self.scope.get('scheme') == 'wss':
            proto = 'https'
            
        return f"{proto}://{host}{message.file.url}"

    @database_sync_to_async
    def create_job_if_not_exists(self, room_id):
        from jobs.models import Job
        room = ChatRoom.objects.get(id=room_id)
        active_job = Job.objects.filter(
            customer=room.customer,
            professional=room.professional,
            status__in=[Job.Status.REQUESTED, Job.Status.AGREED, Job.Status.IN_VISIT]
        ).first()

        if not active_job:
            job = Job.objects.create(
                customer=room.customer,
                professional=room.professional,
                status=Job.Status.REQUESTED
            )
            room.job = job
            room.save()
            return True
        else:
            if room.job != active_job:
                room.job = active_job
                room.save()
        return False
