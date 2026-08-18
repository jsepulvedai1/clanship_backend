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
        verbose_name="Estado",
        db_index=True
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

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Trabajo"
        verbose_name_plural = "Trabajos"
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['professional', 'status']),
        ]

    def __str__(self):
        return f"Trabajo {self.id}: {self.customer.username} - {self.professional.username}"

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Job)
def notify_job_saved(sender, instance, created, **kwargs):
    """
    Despacha la tarea asíncrona de Celery para enviar notificaciones WebSocket y FCM.
    No bloquea la transacción de base de datos ni la respuesta HTTP.
    """
    try:
        from core.tasks import process_job_saved_notifications
        process_job_saved_notifications.delay(instance.id, created)
    except Exception as e:
        # Fallback de seguridad si Celery no está disponible
        import logging
        logging.getLogger(__name__).warning(f"Could not enqueue job notification task to Celery: {e}")
        try:
            from core.tasks import process_job_saved_notifications
            process_job_saved_notifications(instance.id, created)
        except Exception as fallback_err:
            logging.getLogger(__name__).error(f"Fallback notification failed: {fallback_err}")


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


class PublicJobRequest(models.Model):
    """
    Solicitud abierta de trabajo / Oportunidad publicada por un cliente.
    """
    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Abierta'
        ASSIGNED = 'ASSIGNED', 'Asignada'
        CANCELLED = 'CANCELLED', 'Cancelada'
        EXPIRED = 'EXPIRED', 'Expirada'

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="public_job_requests",
        verbose_name="Cliente"
    )
    specialty = models.ForeignKey(
        'users.Specialty',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="public_job_requests",
        verbose_name="Especialidad requerida"
    )
    custom_specialty = models.CharField(max_length=150, null=True, blank=True, verbose_name="Especialidad personalizada")
    title = models.CharField(max_length=150, verbose_name="Título del servicio")
    description = models.TextField(verbose_name="Descripción detallada")
    address = models.CharField(max_length=255, verbose_name="Dirección de la visita")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Latitud")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, verbose_name="Longitud")
    photo = models.ImageField(upload_to="public_job_photos/", null=True, blank=True, verbose_name="Fotografía del problema")
    photos = models.JSONField(default=list, blank=True, verbose_name="Fotografías del problema (máximo 4)")
    desired_date = models.DateField(null=True, blank=True, verbose_name="Fecha deseada del trabajo")
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Presupuesto estimado")
    is_urgent = models.BooleanField(default=False, verbose_name="Urgente")
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
        verbose_name="Estado"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de expiración")

    class Meta:
        verbose_name = "Solicitud Abierta"
        verbose_name_plural = "Solicitudes Abiertas"

    def __str__(self):
        return f"Solicitud Abierta {self.id}: {self.title} ({self.customer.username})"


class JobProposal(models.Model):
    """
    Postulación / Cotización enviada por un maestro a una solicitud abierta.
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente'
        ACCEPTED = 'ACCEPTED', 'Aceptada'
        REJECTED = 'REJECTED', 'Rechazada'

    public_request = models.ForeignKey(
        PublicJobRequest,
        on_delete=models.CASCADE,
        related_name="proposals",
        verbose_name="Solicitud Abierta"
    )
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="job_proposals",
        verbose_name="Profesional"
    )
    estimated_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio cotizado")
    scheduled_date = models.DateField(verbose_name="Fecha propuesta")
    scheduled_time = models.TimeField(verbose_name="Hora propuesta")
    message = models.TextField(blank=True, verbose_name="Mensaje para el cliente")
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Estado de la propuesta"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Propuesta de Trabajo"
        verbose_name_plural = "Propuestas de Trabajo"
        unique_together = ('public_request', 'professional')

    def __str__(self):
        return f"Propuesta {self.id} de {self.professional.username} para Solicitud #{self.public_request_id}"


