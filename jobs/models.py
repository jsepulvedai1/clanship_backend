from django.db import models
from django.conf import settings

class Job(models.Model):
    """
    Representa un trabajo o servicio acordado entre cliente y profesional.
    """
    class Status(models.TextChoices):
        REQUESTED = 'REQUESTED', 'Solicitado'
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
    agreed_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name="Precio acordado",
        null=True, blank=True
    )
    address = models.CharField(max_length=255, verbose_name="Dirección de la visita", null=True, blank=True)
    is_read = models.BooleanField(default=False, verbose_name="Leído por el profesional")
    
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

@receiver(post_save, sender=Job)
def notify_job_saved(sender, instance, created, **kwargs):
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f"user_{instance.professional.id}",
                {
                    "type": "job_notification",
                    "event": "job_created" if created else "job_updated",
                    "job_id": instance.id,
                    "message": "Nuevo trabajo recibido" if created else "El estado del trabajo ha cambiado"
                }
            )
    except Exception as e:
        print(f"Error al enviar notificacion por WS: {e}")
