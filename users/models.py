from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings

class User(AbstractUser):
    """
    Modelo de usuario personalizado para Clanship.
    """
    class UserType(models.TextChoices):
        CUSTOMER = 'CUSTOMER', 'Cliente'
        PROFESSIONAL = 'PROFESSIONAL', 'Profesional'
        ADMIN = 'ADMIN', 'Administrador'

    phone_number = models.CharField(
        max_length=15, 
        unique=True, 
        verbose_name="Número de Teléfono",
        null=True, blank=True
    )
    user_type = models.CharField(
        max_length=20,
        choices=UserType.choices,
        default=UserType.CUSTOMER,
        verbose_name="Tipo de Usuario"
    )
    avatar = models.ImageField(
        upload_to='avatars/', 
        null=True, blank=True, 
        verbose_name="Foto de Perfil"
    )
    latitude = models.DecimalField(
        max_digits=12, 
        decimal_places=9, 
        null=True, blank=True, 
        verbose_name="Latitud"
    )
    longitude = models.DecimalField(
        max_digits=12, 
        decimal_places=9, 
        null=True, blank=True, 
        verbose_name="Longitud"
    )
    address = models.CharField(
        max_length=255, 
        null=True, blank=True, 
        verbose_name="Dirección"
    )
    is_available = models.BooleanField(
        default=False, 
        verbose_name="Disponible para trabajos"
    )

    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"


class Specialty(models.Model):
    """
    Especialidades de los profesionales (ej: Electricista, Pintor).
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Nombre")
    icon = models.CharField(max_length=100, help_text="Nombre del icono (ej: electric_bolt)", null=True, blank=True)

    class Meta:
        verbose_name = "Especialidad"
        verbose_name_plural = "Especialidades"

    def __str__(self):
        return self.name


class ProfessionalProfile(models.Model):
    """
    Perfil detallado para usuarios de tipo PROFESIONAL.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="professional_profile"
    )
    specialty = models.ForeignKey(
        Specialty, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name="professionals"
    )
    bio = models.TextField(max_length=500, verbose_name="Biografía", null=True, blank=True)
    hourly_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="Tarifa por hora", 
        null=True, blank=True
    )
    rating = models.FloatField(default=0.0, verbose_name="Calificación")
    is_verified = models.BooleanField(default=False, verbose_name="Verificado")

    class Meta:
        verbose_name = "Perfil Profesional"
        verbose_name_plural = "Perfiles Profesionales"

    def __str__(self):
        return f"Perfil de {self.user.username} - {self.specialty}"
