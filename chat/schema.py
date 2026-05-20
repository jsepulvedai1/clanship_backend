import graphene
from graphene_django import DjangoObjectType
from .models import ChatRoom, Message
from django.contrib.auth import get_user_model
from graphql_jwt.decorators import login_required
from django.db.models import Q
import channels_graphql_ws

User = get_user_model()

class ChatRoomType(DjangoObjectType):
    class Meta:
        model = ChatRoom
        fields = "__all__"

class MessageType(DjangoObjectType):
    class Meta:
        model = Message
        fields = "__all__"

class OnNewMessage(channels_graphql_ws.Subscription):
    """
    Suscripción para recibir nuevos mensajes en tiempo real.
    """
    message = graphene.Field(MessageType)

    class Arguments:
        room_id = graphene.Int(required=True)

    @staticmethod
    def subscribe(root, info, room_id):
        """
        Se llama cuando un cliente se suscribe.
        """
        # Aquí se puede validar si el usuario tiene permiso para la sala
        return [f"room_{room_id}"]

    @staticmethod
    def publish(payload, info, room_id):
        """
        Se llama cuando se emite un mensaje.
        """
        return OnNewMessage(message=payload)


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

        # Emitir el mensaje a la suscripción
        OnNewMessage.broadcast(
            group=f"room_{room_id}",
            payload=message
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

class Subscription(graphene.ObjectType):
    on_new_message = OnNewMessage.Field()

class Mutation(graphene.ObjectType):
    send_message = SendMessage.Field()
    get_or_create_chat_room = GetOrCreateChatRoom.Field()
