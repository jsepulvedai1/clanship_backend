import graphene
from graphene_django import DjangoObjectType
from .models import ChatRoom, Message
from django.contrib.auth import get_user_model
from graphql_jwt.decorators import login_required
from django.db.models import Q

User = get_user_model()

class ChatRoomType(DjangoObjectType):
    class Meta:
        model = ChatRoom
        fields = "__all__"

class MessageType(DjangoObjectType):
    class Meta:
        model = Message
        fields = "__all__"


class SendMessage(graphene.Mutation):
    class Arguments:
        room_id = graphene.Int(required=True)
        text = graphene.String(required=True)

    message = graphene.Field(MessageType)

    @login_required
    def mutate(self, info, room_id, text):
        user = info.context.user
        try:
            room = ChatRoom.objects.get(pk=room_id)
        except ChatRoom.DoesNotExist:
            raise Exception("La sala de chat no existe.")

        if room.customer != user and room.professional != user:
            raise Exception("No perteneces a esta sala.")

        message = Message.objects.create(
            room=room,
            sender=user,
            text=text
        )

        # Broadcast the message to Channels WebSocket clients in the same room group
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"chat_{room_id}",
                {
                    'type': 'chat_message',
                    'message': message.text,
                    'sender_id': user.id,
                    'sender_username': user.username,
                    'created_at': message.created_at.isoformat()
                }
            )

        return SendMessage(message=message)

# ... (El resto de la clase Mutation y Query se mantiene)

class GetOrCreateChatRoom(graphene.Mutation):
    class Arguments:
        professional_id = graphene.Int(required=True)

    room = graphene.Field(ChatRoomType)

    @login_required
    def mutate(self, info, professional_id):
        user = info.context.user
        try:
            professional = User.objects.get(pk=professional_id, user_type='PROFESSIONAL')
        except User.DoesNotExist:
            raise Exception("Profesional no encontrado.")

        room, created = ChatRoom.objects.get_or_create(
            customer=user,
            professional=professional
        )
        return GetOrCreateChatRoom(room=room)

class GetOrCreateChatRoomWithCustomer(graphene.Mutation):
    class Arguments:
        customer_id = graphene.Int(required=True)

    room = graphene.Field(ChatRoomType)

    @login_required
    def mutate(self, info, customer_id):
        user = info.context.user
        if user.user_type != 'PROFESSIONAL':
            raise Exception("Solo los profesionales pueden iniciar un chat con un cliente usando esta mutación.")
            
        try:
            customer = User.objects.get(pk=customer_id)
        except User.DoesNotExist:
            raise Exception("Cliente no encontrado.")

        room, created = ChatRoom.objects.get_or_create(
            customer=customer,
            professional=user
        )
        return GetOrCreateChatRoomWithCustomer(room=room)

class Query(graphene.ObjectType):
    my_chats = graphene.List(ChatRoomType)
    chat_messages = graphene.List(MessageType, room_id=graphene.Int(required=True))

    @login_required
    def resolve_my_chats(self, info):
        user = info.context.user
        return ChatRoom.objects.filter(Q(customer=user) | Q(professional=user))

    @login_required
    def resolve_chat_messages(self, info, room_id):
        user = info.context.user
        try:
            room = ChatRoom.objects.get(pk=room_id)
            if room.customer == user or room.professional == user:
                return Message.objects.filter(room=room).order_by('created_at')
            raise Exception("No tienes acceso a esta sala.")
        except ChatRoom.DoesNotExist:
            return Message.objects.none()



class Mutation(graphene.ObjectType):
    send_message = SendMessage.Field()
    get_or_create_chat_room = GetOrCreateChatRoom.Field()
    get_or_create_chat_room_with_customer = GetOrCreateChatRoomWithCustomer.Field()
