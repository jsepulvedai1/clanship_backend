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
        on_delete=models.CASCADE,
        related_name="chat_room",
        null=True,
        blank=True,
        verbose_name="Trabajo asociado"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sala de Chat"
        verbose_name_plural = "Salas de Chat"

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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Mensaje"
        verbose_name_plural = "Mensajes"
        ordering = ['created_at']

    def __str__(self):
        return f"De {self.sender.username} en {self.room}"


from django.db.models.signals import post_save
from django.dispatch import receiver
from core.firebase import send_push_notification

@receiver(post_save, sender=Message)
def notify_message_saved(sender, instance, created, **kwargs):
    if created:
        try:
            room = instance.room
            recipient = room.professional if instance.sender == room.customer else room.customer
            if recipient and recipient.fcm_token:
                sender_name = instance.sender.get_full_name() or instance.sender.username
                body_text = instance.text or ""
                if instance.message_type == 'IMAGE':
                    body_text = "📷 Foto"
                elif instance.message_type == 'AUDIO':
                    body_text = "🎤 Mensaje de voz"
                
                send_push_notification(
                    fcm_token=recipient.fcm_token,
                    title=f"Mensaje de {sender_name}",
                    body=body_text,
                    data={
                        "event": "chat_message",
                        "room_id": str(room.id),
                        "job_id": str(room.job.id) if room.job else ""
                    }
                )
        except Exception as e:
            print(f"Error in notify_message_saved signal: {e}")

