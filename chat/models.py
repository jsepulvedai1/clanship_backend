from django.db import models
from django.conf import settings

class ChatRoom(models.Model):
    """
    Sala de chat entre un cliente y un profesional.
    """
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="customer_chats"
    )
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="professional_chats"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sala de Chat"
        verbose_name_plural = "Salas de Chat"
        unique_together = ('customer', 'professional')

    def __str__(self):
        return f"Chat: {self.customer.username} & {self.professional.username}"


class Message(models.Model):
    """
    Mensajes individuales dentro de una sala de chat.
    """
    room = models.ForeignKey(
        ChatRoom, 
        on_delete=models.CASCADE, 
        related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE
    )
    text = models.TextField(verbose_name="Mensaje")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mensaje"
        verbose_name_plural = "Mensajes"
        ordering = ['created_at']

    def __str__(self):
        return f"De {self.sender.username} en {self.room}"
