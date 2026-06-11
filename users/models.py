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
    fcm_token = models.CharField(
        max_length=255,
        null=True, blank=True,
        verbose_name="Token Firebase Cloud Messaging"
    )
    favorite_professionals = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name="favorited_by_users",
        verbose_name="Profesionales Favoritos"
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


class Tag(models.Model):
    """
    Etiquetas para asociar con profesionales (ej: cableado, grifería, pintura_exterior).
    """
    name = models.CharField(max_length=50, unique=True, verbose_name="Nombre")

    class Meta:
        verbose_name = "Etiqueta"
        verbose_name_plural = "Etiquetas"

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
    
    # Redes sociales
    facebook_url = models.URLField(max_length=255, null=True, blank=True, verbose_name="Facebook URL")
    instagram_url = models.URLField(max_length=255, null=True, blank=True, verbose_name="Instagram URL")
    tiktok_url = models.URLField(max_length=255, null=True, blank=True, verbose_name="TikTok URL")
    
    # Radio de servicio y etiquetas asociadas
    service_radius = models.IntegerField(default=10, verbose_name="Radio de servicio (km)")
    tags = models.ManyToManyField(Tag, blank=True, related_name="professionals", verbose_name="Etiquetas")

    class Meta:
        verbose_name = "Perfil Profesional"
        verbose_name_plural = "Perfiles Profesionales"

    def __str__(self):
        return f"Perfil de {self.user.username} - {self.specialty}"


class ProfessionalPhoto(models.Model):
    """
    Fotografías de trabajos anteriores o portafolio de un profesional.
    """
    profile = models.ForeignKey(
        ProfessionalProfile,
        on_delete=models.CASCADE,
        related_name="photos",
        verbose_name="Perfil Profesional"
    )
    image = models.ImageField(
        upload_to='portfolio/',
        verbose_name="Imagen de Portafolio"
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de carga"
    )

    class Meta:
        verbose_name = "Foto de Portafolio"
        verbose_name_plural = "Fotos de Portafolio"

    def __str__(self):
        return f"Foto {self.id} de {self.profile.user.username}"


class ProfessionalDocument(models.Model):
    """
    Certificados, títulos y documentos profesionales de un maestro.
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente'
        APPROVED = 'APPROVED', 'Aprobado'
        REJECTED = 'REJECTED', 'Rechazado'

    profile = models.ForeignKey(
        ProfessionalProfile,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name="Perfil Profesional"
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Nombre del Documento"
    )
    file = models.FileField(
        upload_to='documents/',
        verbose_name="Archivo del Documento"
    )
    is_visible = models.BooleanField(
        default=True,
        verbose_name="Visible en Perfil Público"
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name="Estado de Validación"
    )
    rejection_reason = models.TextField(
        blank=True,
        null=True,
        verbose_name="Motivo de Rechazo"
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de Carga"
    )

    class Meta:
        verbose_name = "Documento Profesional"
        verbose_name_plural = "Documentos Profesionales"

    def __str__(self):
        return f"{self.name} ({self.get_status_display()}) - {self.profile.user.username}"


