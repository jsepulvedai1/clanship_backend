from django.db import models
from django.conf import settings

class Job(models.Model):
    """
    Representa un trabajo o servicio acordado entre cliente y profesional.
    """
    class Status(models.TextChoices):
        REQUESTED = 'REQUESTED', 'Solicitado'
        SCHEDULED = 'SCHEDULED', 'Propuesto por Confirmar'
        AGREED = 'AGREED', 'Acordado'
        IN_VISIT = 'IN_VISIT', 'En Visita'
        FINISHED = 'FINISHED', 'Finalizado'
        CANCELLED = 'CANCELLED', 'Cancelado'

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="customer_jobs"
    )
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="professional_jobs"
    )
    
    # Agenda
    scheduled_date = models.DateField(verbose_name="Fecha programada", null=True, blank=True)
    scheduled_time = models.TimeField(verbose_name="Hora programada", null=True, blank=True)
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REQUESTED,
        verbose_name="Estado"
    )
    
    description = models.TextField(verbose_name="Descripción del trabajo", blank=True)
    enriched_details = models.TextField(null=True, blank=True, verbose_name="Detalles adicionales")
    additional_photo = models.ImageField(upload_to="job_photos/", null=True, blank=True, verbose_name="Foto adicional")
    notification_lead_minutes = models.IntegerField(default=60, verbose_name="Minutos de aviso push previo")
    lead_notification_sent = models.BooleanField(default=False, verbose_name="Notificación de aviso previo enviada")
    agreed_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name="Precio acordado",
        null=True, blank=True
    )
    address = models.CharField(max_length=255, verbose_name="Dirección de la visita", null=True, blank=True)
    is_read = models.BooleanField(default=False, verbose_name="Leído por el profesional")
    cancellation_reason = models.TextField(null=True, blank=True, verbose_name="Razón de cancelación/rechazo")
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="cancelled_jobs",
        verbose_name="Cancelado por"
    )
    
    # Podríamos añadir PointField aquí cuando GDAL esté disponible
    # location = models.PointField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Trabajo"
        verbose_name_plural = "Trabajos"

    def __str__(self):
        return f"Trabajo {self.id}: {self.customer.username} - {self.professional.username}"

from django.db.models.signals import post_save
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from core.firebase import send_user_push_notification

@receiver(post_save, sender=Job)
def notify_job_saved(sender, instance, created, **kwargs):
    # 1. Notificación en tiempo real por WebSockets (para la UI activa)
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            # Enviar a ambos (cliente y profesional)
            for user in [instance.customer, instance.professional]:
                async_to_sync(channel_layer.group_send)(
                    f"user_{user.id}",
                    {
                        "type": "job_notification",
                        "event": "job_created" if created else "job_updated",
                        "job_id": instance.id,
                        "status": instance.status,
                        "message": "Nuevo trabajo recibido" if created else "El estado del trabajo ha cambiado"
                    }
                )

            # Si el trabajo tiene sala de chat asociada, emitir a la sala en tiempo real
            chat_room = getattr(instance, 'chat_room', None)
            if not chat_room:
                from chat.models import ChatRoom
                chat_room = ChatRoom.objects.filter(customer=instance.customer, professional=instance.professional).first()

            if chat_room:
                cancelled_by_str = instance.cancelled_by_user.get_full_name() if instance.cancelled_by_user else None
                async_to_sync(channel_layer.group_send)(
                    f"chat_{chat_room.id}",
                    {
                        "type": "job_status_changed",
                        "event": "JOB_STATUS_CHANGED",
                        "job_id": instance.id,
                        "new_status": instance.status,
                        "cancellation_reason": instance.cancellation_reason,
                        "cancelled_by": cancelled_by_str
                    }
                )
    except Exception as e:
        print(f"Error al enviar notificacion por WS: {e}")

    # 2. Notificaciones push por Firebase Messaging (FCM)
    try:
        if created:
            # Notificar al profesional de una nueva solicitud
            prof = instance.professional
            if prof:
                client_name = instance.customer.get_full_name() or instance.customer.username
                send_user_push_notification(
                    user=prof,
                    title="Nueva solicitud de trabajo",
                    body=f"Tienes una nueva solicitud de {client_name}.",
                    data={"event": "job_created", "job_id": instance.id}
                )
        elif instance.status == Job.Status.CANCELLED:
            # Notificar al cliente que su solicitud fue rechazada/cancelada
            cust = instance.customer
            if cust:
                prof_name = instance.professional.get_full_name() or instance.professional.username
                send_user_push_notification(
                    user=cust,
                    title="Solicitud Rechazada",
                    body=f"Tu solicitud con {prof_name} ha sido cancelada o rechazada.",
                    data={"event": "job_cancelled", "job_id": instance.id}
                )
    except Exception as e:
        print(f"Error al enviar notificacion por Firebase: {e}")


class JobReview(models.Model):
    """
    Calificación y reseña asignada a un trabajo finalizado.
    """
    job = models.OneToOneField(
        Job,
        on_delete=models.CASCADE,
        related_name="review",
        verbose_name="Trabajo"
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews_given",
        verbose_name="Cliente"
    )
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews_received",
        verbose_name="Profesional"
    )
    rating = models.IntegerField(verbose_name="Calificación (1-5)")
    comment = models.TextField(null=True, blank=True, verbose_name="Comentario")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Calificación de Trabajo"
        verbose_name_plural = "Calificaciones de Trabajos"

    def __str__(self):
        return f"Reseña {self.rating}★ para {self.professional.username} (Trabajo #{self.job_id})"


@receiver(post_save, sender=JobReview)
def update_professional_rating(sender, instance, created, **kwargs):
    from django.db.models import Avg
    prof_user = instance.professional
    prof_profile = getattr(prof_user, 'professional_profile', None)
    if prof_profile:
        reviews = JobReview.objects.filter(professional=prof_user)
        avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0.0
        prof_profile.rating = round(float(avg_rating), 1)
        prof_profile.save(update_fields=['rating'])

