from django.db import models
from django.conf import settings

class Job(models.Model):
    """
    Representa un trabajo o servicio acordado entre cliente y profesional.
    """
    class Status(models.TextChoices):
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
    scheduled_date = models.DateField(verbose_name="Fecha programada")
    scheduled_time = models.TimeField(verbose_name="Hora programada")
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AGREED,
        verbose_name="Estado"
    )
    
    description = models.TextField(verbose_name="Descripción del trabajo")
    agreed_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name="Precio acordado"
    )
    address = models.CharField(max_length=255, verbose_name="Dirección de la visita")
    
    # Podríamos añadir PointField aquí cuando GDAL esté disponible
    # location = models.PointField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Trabajo"
        verbose_name_plural = "Trabajos"

    def __str__(self):
        return f"Trabajo {self.id}: {self.customer.username} - {self.professional.username}"
