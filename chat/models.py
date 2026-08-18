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
    job = models.OneToOneField(
        "jobs.Job",
        on_delete=models.SET_NULL,
        related_name="chat_room",
        null=True,
        blank=True,
        verbose_name="Trabajo asociado"
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
    text = models.TextField(verbose_name="Mensaje", blank=True, null=True)
    file = models.FileField(upload_to='chat_files/', null=True, blank=True, verbose_name="Archivo adjunto")
    message_type = models.CharField(
        max_length=10,
        choices=[('TEXT', 'Texto'), ('IMAGE', 'Imagen'), ('AUDIO', 'Audio')],
        default='TEXT',
        verbose_name="Tipo de mensaje"
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Mensaje"
        verbose_name_plural = "Mensajes"
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['room', 'created_at']),
        ]

    def __str__(self):
        return f"De {self.sender.username} en {self.room}"


from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Message)
def notify_message_saved(sender, instance, created, **kwargs):
    """
    Despacha la tarea asíncrona de Celery para enviar notificaciones WebSocket y FCM.
    No bloquea la transacción del mensaje ni la respuesta HTTP.
    """
    if created:
        try:
            from core.tasks import process_chat_message_notifications
            process_chat_message_notifications.delay(instance.id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not enqueue chat notification task to Celery: {e}")

