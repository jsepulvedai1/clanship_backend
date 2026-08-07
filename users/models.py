from django.db import models
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.utils import timezone

class User(AbstractUser):
    """
    Modelo de usuario personalizado para Clanship.
    """
    class UserType(models.TextChoices):
        CUSTOMER = 'CUSTOMER', 'Cliente'
        PROFESSIONAL = 'PROFESSIONAL', 'Profesional'
        ADMIN = 'ADMIN', 'Administrador'

    first_name = models.CharField(
        max_length=30,
        verbose_name="Nombre",
        blank=True
    )
    last_name = models.CharField(
        max_length=30,
        verbose_name="Apellido",
        blank=True
    )

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
    is_emergency = models.BooleanField(
        default=False, 
        verbose_name="Modo Urgencia"
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
    client_session_key = models.CharField(
        max_length=255, 
        null=True, blank=True, 
        verbose_name="Clave de Sesión Cliente Activa"
    )
    tradesman_session_key = models.CharField(
        max_length=255, 
        null=True, blank=True, 
        verbose_name="Clave de Sesión Maestro Activa"
    )

    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"


class Specialty(models.Model):
    """
    Especialidades de los profesionales (ej: Electricista, Pintor).
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Nombre")
    icon = models.ImageField(upload_to="specialty_icons/", null=True, blank=True, verbose_name="Icono")
    color = models.CharField(
        max_length=7,
        default="#0B6E4F",
        verbose_name="Color hexadecimal",
        help_text="Color para la especialidad/etiqueta en formato hexadecimal (ej: #FF5733)"
    )
    synonyms = models.TextField(
        blank=True,
        null=True,
        verbose_name="Sub-etiquetas ocultas",
        help_text="Sinónimos o palabras clave de búsqueda separadas por comas (ej: electricidad, corriente)"
    )

    class Meta:
        verbose_name = "Especialidad"
        verbose_name_plural = "Especialidades"

    def __str__(self):
        return self.name


class Tag(models.Model):
    """
    Etiquetas para asociar con profesionales (ej: cableado, grifería, pintura_exterior).
    """
    name = models.CharField(max_length=100, unique=True, verbose_name="Nombre")
    specialty = models.ForeignKey(
        Specialty,
        on_delete=models.CASCADE,
        related_name="tags",
        verbose_name="Clase (Especialidad)",
        null=True,
        blank=True
    )
    synonyms = models.TextField(
        blank=True,
        null=True,
        verbose_name="Sub-etiquetas ocultas",
        help_text="Sinónimos o palabras clave de búsqueda separadas por comas (ej: gafiter, plomeria, cañeria)"
    )
    color = models.CharField(
        max_length=7,
        default="#0B6E4F",
        verbose_name="Color hexadecimal",
        help_text="Color para la etiqueta en formato hexadecimal (ej: #FF5733)"
    )
    icon = models.ImageField(upload_to="tag_icons/", null=True, blank=True, verbose_name="Icono")

    class Meta:
        verbose_name = "Etiqueta"
        verbose_name_plural = "Etiquetas"

    def __str__(self):
        return self.name


class SubTag(models.Model):
    """
    Sub-etiquetas o especializaciones específicas dentro de una etiqueta principal.
    """
    name = models.CharField(max_length=150, verbose_name="Nombre")
    tag = models.ForeignKey(
        Tag,
        on_delete=models.CASCADE,
        related_name="subtags",
        verbose_name="Etiqueta Principal (Subclase)"
    )
    color = models.CharField(
        max_length=7,
        default="#0B6E4F",
        verbose_name="Color hexadecimal",
        help_text="Color para la sub-etiqueta en formato hexadecimal (ej: #FF5733)"
    )

    class Meta:
        verbose_name = "Especialización (Sub-etiqueta)"
        verbose_name_plural = "Especializaciones (Sub-etiquetas)"
        unique_together = ('tag', 'name')

    def __str__(self):
        return f"{self.tag.name} -> {self.name}"


class SubscriptionPlan(models.Model):
    """
    Planes de suscripción para los profesionales.
    """
    name = models.CharField(max_length=100, verbose_name="Nombre")
    description = models.TextField(blank=True, null=True, verbose_name="Descripción")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Precio")
    duration_days = models.IntegerField(default=30, verbose_name="Duración (días)")
    
    # Parámetros del plan
    monthly_requests = models.IntegerField(blank=True, null=True, verbose_name="Solicitudes mensuales", help_text="Nulo/vacío para ilimitadas")
    urgent_requests = models.IntegerField(blank=True, null=True, verbose_name="Solicitudes urgentes", help_text="Nulo/vacío para ilimitadas")
    service_categories = models.IntegerField(blank=True, null=True, verbose_name="Categorías de servicio", help_text="Nulo/vacío para ilimitadas")
    max_completed_jobs = models.IntegerField(blank=True, null=True, verbose_name="Límite de trabajos terminados", help_text="Nulo para ilimitados. Usado principalmente para planes iniciales.")
    search_position = models.CharField(max_length=100, default="Estándar", verbose_name="Posición en búsquedas")
    featured_badge = models.CharField(max_length=100, blank=True, null=True, default="—", verbose_name="Insignia destacada")
    rrss_campaigns = models.CharField(max_length=100, blank=True, null=True, default="—", verbose_name="Aparición en campañas RRSS")
    radio_broadcast = models.CharField(max_length=100, blank=True, null=True, default="—", verbose_name="Difusión radial")
    profile_statistics = models.CharField(max_length=100, default="Básicas", verbose_name="Estadísticas del perfil")
    support_level = models.CharField(max_length=100, default="Estándar", verbose_name="Soporte")
    is_coming_soon = models.BooleanField(default=False, verbose_name="Próximamente", help_text="Si está activado, el plan se muestra pero no puede ser seleccionado.")
    display_order = models.IntegerField(default=0, verbose_name="Orden de visualización", help_text="Menor número aparece primero (1, 2, 3...).")

    class Meta:
        verbose_name = "Plan de Suscripción"
        verbose_name_plural = "Planes de Suscripción"
        ordering = ['display_order', 'id']

    def __str__(self):
        return f"{self.name} (${self.price})"


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
        related_name="professionals",
        verbose_name="Especialidad Principal"
    )
    specialties = models.ManyToManyField(
        Specialty,
        blank=True,
        related_name="profile_specialties",
        verbose_name="Especialidades"
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="professionals",
        verbose_name="Plan de Suscripción"
    )
    plan_start_date = models.DateTimeField(default=timezone.now, verbose_name="Fecha de inicio del plan")
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
    
    # Ubicación del taller / trabajo profesional
    address = models.CharField(
        max_length=255, 
        null=True, blank=True, 
        verbose_name="Dirección Profesional / Taller"
    )
    latitude = models.DecimalField(
        max_digits=12, 
        decimal_places=9, 
        null=True, blank=True, 
        verbose_name="Latitud Profesional"
    )
    longitude = models.DecimalField(
        max_digits=12, 
        decimal_places=9, 
        null=True, blank=True, 
        verbose_name="Longitud Profesional"
    )

    # Radio de servicio y etiquetas asociadas
    service_radius = models.IntegerField(default=10, verbose_name="Radio de servicio (km)")
    tags = models.ManyToManyField(Tag, blank=True, related_name="professionals", verbose_name="Etiquetas")
    subtags = models.ManyToManyField(SubTag, blank=True, related_name="professionals", verbose_name="Especializaciones")

    class Meta:
        verbose_name = "Perfil Profesional"
        verbose_name_plural = "Perfiles Profesionales"

    def __str__(self):
        return f"Perfil de {self.user.username} - {self.specialty}"

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_is_verified = False
        if not is_new:
            try:
                old_is_verified = ProfessionalProfile.objects.get(pk=self.pk).is_verified
            except Exception:
                pass

        if not self.plan_id:
            plan, _ = SubscriptionPlan.objects.get_or_create(
                name="Plan Base",
                defaults={
                    "description": "Plan básico gratuito",
                    "price": 0.00,
                    "duration_days": 3650,
                }
            )
            self.plan = plan
        super().save(*args, **kwargs)

        if is_new or (old_is_verified != self.is_verified):
            self.notify_validation_status()

    def notify_validation_status(self):
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer and self.user_id:
                async_to_sync(channel_layer.group_send)(
                    f'user_{self.user_id}',
                    {
                        'type': 'job_notification',
                        'event': 'profile_validated' if self.is_verified else 'profile_unvalidated',
                        'job_id': 0,
                        'message': '¡Tu perfil profesional ha sido validado! Ya puedes activarte.' if self.is_verified else 'Tu estado de validación ha cambiado.',
                        'is_validated': self.is_verified,
                    }
                )
        except Exception as e:
            print(f"Error sending validation websocket notification: {e}")


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


class UserAddress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saved_addresses", verbose_name="Usuario")
    address = models.CharField(max_length=255, verbose_name="Dirección")
    latitude = models.FloatField(verbose_name="Latitud")
    longitude = models.FloatField(verbose_name="Longitud")
    alias = models.CharField(max_length=50, blank=True, null=True, verbose_name="Alias", help_text="Ej: Hogar, Trabajo")

    class Meta:
        verbose_name = "Dirección de Usuario"
        verbose_name_plural = "Direcciones de Usuario"

    def __str__(self):
        return f"{self.alias or 'Dirección'} - {self.user.username}"


class SystemSetting(models.Model):
    """
    Configuración global del sistema modificable desde Django Admin.
    """
    max_specialties_per_tradesman = models.PositiveIntegerField(
        default=6,
        verbose_name="Máximo de especialidades por maestro",
        help_text="Número máximo de especialidades/subtags que puede seleccionar un maestro"
    )

    class Meta:
        verbose_name = "Configuración del Sistema"
        verbose_name_plural = "Configuración del Sistema"

    def __str__(self):
        return f"Configuración del Sistema (Máx. Especialidades: {self.max_specialties_per_tradesman})"

    @classmethod
    def get_max_specialties(cls):
        setting = cls.objects.first()
        return setting.max_specialties_per_tradesman if setting else 6


from django.db.models.signals import m2m_changed
from django.core.exceptions import ValidationError
from django.dispatch import receiver

@receiver(m2m_changed, sender=ProfessionalProfile.subtags.through)
def limit_subtags_and_sync_tags(sender, instance, action, **kwargs):
    if action == "pre_add":
        pk_set = kwargs.get("pk_set", set())
        current_subtags = set(instance.subtags.values_list('id', flat=True))
        new_subtags = current_subtags.union(pk_set)
        max_limit = SystemSetting.get_max_specialties()
        if len(new_subtags) > max_limit:
            raise ValidationError(f"No puedes seleccionar más de {max_limit} especializaciones.")

    if action in ["post_add", "post_remove", "post_clear"]:
        parent_tag_ids = list(instance.subtags.values_list('tag_id', flat=True).distinct())
        instance.tags.set(parent_tag_ids)
        parent_specialty_ids = list(Tag.objects.filter(id__in=parent_tag_ids, specialty_id__isnull=False).values_list('specialty_id', flat=True).distinct())
        instance.specialties.set(parent_specialty_ids)


import uuid

class PasswordResetOTP(models.Model):
    email = models.EmailField(verbose_name="Correo electrónico")
    otp_code = models.CharField(max_length=6, verbose_name="Código OTP")
    reset_token = models.UUIDField(default=uuid.uuid4, unique=True, verbose_name="Token de cambio")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(verbose_name="Fecha de expiración")
    used = models.BooleanField(default=False, verbose_name="Usado")
    verified = models.BooleanField(default=False, verbose_name="Verificado")

    class Meta:
        verbose_name = "OTP de recuperación de contraseña"
        verbose_name_plural = "OTPs de recuperación de contraseña"

    def __str__(self):
        return f"OTP para {self.email} - {'Usado' if self.used else 'Activo'}"

    def is_valid(self):
        from django.utils import timezone
        return not self.used and timezone.now() < self.expires_at


class UserDevice(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="devices",
        verbose_name="Usuario"
    )
    fcm_token = models.CharField(
        max_length=500,
        unique=True,
        verbose_name="Token Firebase Cloud Messaging"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Dispositivo de Usuario"
        verbose_name_plural = "Dispositivos de Usuario"

    def __str__(self):
        return f"{self.user.username} - {self.fcm_token[:20]}..."



