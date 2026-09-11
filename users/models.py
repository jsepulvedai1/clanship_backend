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
        verbose_name="Tipo de Usuario",
        db_index=True
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
        verbose_name="Disponible para trabajos",
        db_index=True
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
    blocked_users = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=False,
        related_name="blocked_by",
        verbose_name="Usuarios Bloqueados"
    )
    client_session_key = models.CharField(
        max_length=255, 
        null=True, blank=True, 
        verbose_name="Clave de Sesión Cliente Activa",
        db_index=True
    )
    tradesman_session_key = models.CharField(
        max_length=255, 
        null=True, blank=True, 
        verbose_name="Clave de Sesión Maestro Activa",
        db_index=True
    )

    def get_full_name(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name.title() if full_name else self.username

    def __str__(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        display_name = full_name.title() if full_name else self.username
        return f"{display_name} ({self.get_user_type_display()})"

    def save(self, *args, **kwargs):
        if self.first_name:
            self.first_name = self.first_name.strip().title()
        if self.last_name:
            self.last_name = self.last_name.strip().title()
        super().save(*args, **kwargs)


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
    plan_expires_at = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de expiración del plan / beneficio")
    referral_code = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Código de Asociado",
        db_index=True,
        help_text="Código único para compartir y ganar beneficios por asociados referidos"
    )
    bio = models.TextField(max_length=500, verbose_name="Biografía", null=True, blank=True)
    hourly_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        verbose_name="Tarifa por hora", 
        null=True, blank=True
    )
    rating = models.FloatField(default=0.0, verbose_name="Calificación")
    is_verified = models.BooleanField(default=False, verbose_name="Verificado", db_index=True)

    class VerificationStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente de Revisión'
        APPROVED = 'APPROVED', 'Aprobado / Habilitado'
        REJECTED = 'REJECTED', 'Rechazado / Observado'

    verification_status = models.CharField(
        max_length=20,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
        verbose_name="Estado de Verificación",
        db_index=True
    )
    rejection_reason = models.TextField(
        null=True,
        blank=True,
        verbose_name="Motivo de Rechazo",
        help_text="Motivo por el cual se rechazó o se observaron los documentos/perfil."
    )
    
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

    @classmethod
    def generate_unique_referral_code(cls):
        import secrets
        chars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
        while True:
            code = f"CLAN-{''.join(secrets.choice(chars) for _ in range(5))}"
            if not cls.objects.filter(referral_code=code).exists():
                return code

    @property
    def is_plan_expired(self):
        if not self.plan_expires_at:
            return False
        return timezone.now() > self.plan_expires_at

    @property
    def referrals_total_count(self):
        from users.models import AssociateReferral
        return AssociateReferral.objects.filter(referrer=self.user).count()

    @property
    def referrals_pending_count(self):
        from users.models import AssociateReferral
        return AssociateReferral.objects.filter(referrer=self.user, reward_granted=False).count()

    @property
    def referrals_rewards_earned_count(self):
        from users.models import ReferralRewardLog
        return ReferralRewardLog.objects.filter(professional=self.user).count()

    @property
    def referral_max_rewards_per_user(self):
        from users.models import SystemSetting
        return SystemSetting.get_settings().referral_max_rewards_per_user

    @property
    def referral_has_reached_max_rewards(self):
        limit = self.referral_max_rewards_per_user
        if limit is None or limit <= 0:
            return False
        return self.referrals_rewards_earned_count >= limit

    @property
    def requires_plan_upgrade(self):
        if not self.plan or self.plan.max_completed_jobs is None:
            return False
        
        from jobs.models import Job
        completed_jobs_count = Job.objects.filter(
            professional=self.user,
            status='FINISHED',
            updated_at__gte=self.plan_start_date
        ).count()
        
        return completed_jobs_count >= self.plan.max_completed_jobs

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        old_is_verified = False
        old_status = None
        old_rejection_reason = None
        if not is_new:
            try:
                old_obj = ProfessionalProfile.objects.get(pk=self.pk)
                old_is_verified = old_obj.is_verified
                old_status = old_obj.verification_status
                old_rejection_reason = old_obj.rejection_reason
            except Exception:
                pass

        if not self.referral_code:
            self.referral_code = self.generate_unique_referral_code()

        # Check plan expiration: if promotional/reward plan has expired, revert to Plan Base
        if self.plan_expires_at and timezone.now() > self.plan_expires_at:
            base_plan = SubscriptionPlan.objects.filter(name__in=["Básico", "Plan Base"]).first()
            if base_plan and self.plan_id != base_plan.id:
                self.plan = base_plan
                self.plan_expires_at = None

        # Sync is_verified and verification_status
        if self.is_verified:
            self.verification_status = self.VerificationStatus.APPROVED
            self.rejection_reason = None
        elif self.verification_status == self.VerificationStatus.APPROVED:
            self.is_verified = True
            self.rejection_reason = None

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

        status_changed = (old_is_verified != self.is_verified) or (old_status != self.verification_status) or (old_rejection_reason != self.rejection_reason)
        if is_new or status_changed:
            self.notify_validation_status()

    def notify_validation_status(self):
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            channel_layer = get_channel_layer()
            if channel_layer and self.user_id:
                is_rejected = self.verification_status == self.VerificationStatus.REJECTED or bool(self.rejection_reason)
                if self.is_verified:
                    event = 'profile_validated'
                    message = '¡Tu perfil profesional ha sido validado! Ya puedes activarte.'
                elif is_rejected:
                    event = 'profile_rejected'
                    message = f'Tu registro ha sido observado: {self.rejection_reason}' if self.rejection_reason else 'Tu registro ha sido observado por el equipo de revisión.'
                else:
                    event = 'profile_unvalidated'
                    message = 'Tu estado de validación está en revisión.'

                async_to_sync(channel_layer.group_send)(
                    f'user_{self.user_id}',
                    {
                        'type': 'job_notification',
                        'event': event,
                        'job_id': 0,
                        'message': message,
                        'is_validated': self.is_verified,
                        'verification_status': self.verification_status,
                        'rejection_reason': self.rejection_reason or '',
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
        user_str = getattr(getattr(self.profile, 'user', None), 'username', 'Sin usuario')
        return f"Foto {self.id} de {user_str}"


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
        user_str = getattr(getattr(self.profile, 'user', None), 'username', 'Sin usuario')
        return f"{self.name} ({self.get_status_display()}) - {user_str}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Si este documento se rechaza, sincronizar el estado REJECTED en el perfil profesional
        if self.status == self.Status.REJECTED and self.profile:
            if self.profile.verification_status != ProfessionalProfile.VerificationStatus.REJECTED or not self.profile.rejection_reason:
                self.profile.is_verified = False
                self.profile.verification_status = ProfessionalProfile.VerificationStatus.REJECTED
                reason = self.rejection_reason or f"El documento '{self.name}' no cumple con los requisitos."
                self.profile.rejection_reason = reason
                self.profile.save()


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
    nationwide_coverage_mode = models.BooleanField(
        default=False,
        verbose_name="Modo Cobertura Nacional (Todo Chile)",
        help_text="Si está activo, los clientes pueden ver y contratar a maestros de todo el país, ignorando los límites de radio de movilidad individuales."
    )
    subscriptions_enabled_ios = models.BooleanField(
        default=False,
        verbose_name="Habilitar suscripciones en iOS",
        help_text="Controla si en iOS se muestran compras/suscripciones de planes o vista informativa (Mantener en False para revisión de Apple)"
    )
    subscriptions_min_version_ios = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="Versión mínima para suscripciones en iOS",
        help_text="Versión mínima requerida (ej: 1.0.5) para mostrar planes en iOS. Dejar en blanco si no aplica."
    )
    subscriptions_blocked_versions_ios = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Versiones bloqueadas en iOS (revisión de Apple)",
        help_text="Versiones separadas por coma que NO mostrarán planes (ej: 1.0.6, 1.0.7). Útil cuando una versión específica está en revisión."
    )
    subscriptions_enabled_android = models.BooleanField(
        default=True,
        verbose_name="Habilitar suscripciones en Android",
        help_text="Controla si en Android se muestran los planes de suscripción"
    )
    subscriptions_min_version_android = models.CharField(
        max_length=20,
        blank=True,
        default="",
        verbose_name="Versión mínima para suscripciones en Android",
        help_text="Versión mínima requerida (ej: 1.0.5) para mostrar planes en Android. Dejar en blanco si no aplica."
    )
    subscriptions_blocked_versions_android = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="Versiones bloqueadas en Android",
        help_text="Versiones separadas por coma que NO mostrarán planes en Android (ej: 1.0.6). Dejar en blanco si no aplica."
    )
    subscription_ios_link = models.URLField(
        default="https://clanship.cl",
        verbose_name="Link para información de planes en iOS",
        help_text="URL donde el usuario en iOS puede revisar información de planes"
    )
    subscription_ios_message = models.TextField(
        default="Para una mejor experiencia y conocer cómo mejorar tu plan, revisa en el siguiente link:",
        verbose_name="Mensaje para iOS",
        help_text="Texto informativo que se mostrará en la pantalla de planes en iOS"
    )

    class EligibleReferralUserType(models.TextChoices):
        ALL = 'ALL', 'Todos (Clientes y Maestros)'
        CUSTOMER_ONLY = 'CUSTOMER_ONLY', 'Solo Clientes'
        PROFESSIONAL_ONLY = 'PROFESSIONAL_ONLY', 'Solo Maestros'

    referral_program_active = models.BooleanField(
        default=True,
        verbose_name="Programa de asociados activo",
        help_text="Activa o desactiva el sistema de códigos de asociado"
    )
    referral_target_count = models.PositiveIntegerField(
        default=5,
        verbose_name="Meta de inscritos (N personas)",
        help_text="Cantidad de usuarios que deben registrarse con el código para otorgar el beneficio al maestro"
    )
    referral_reward_plan = models.ForeignKey(
        'users.SubscriptionPlan',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referral_reward_settings",
        verbose_name="Plan otorgado por meta",
        help_text="Plan que ganará el maestro al alcanzar la meta de inscritos"
    )
    referral_reward_days = models.PositiveIntegerField(
        default=30,
        verbose_name="Duración del beneficio (X días)",
        help_text="Días de duración que se otorgarán del plan asociado"
    )
    referral_max_rewards_per_user = models.PositiveIntegerField(
        default=1,
        verbose_name="Límite de beneficios por maestro",
        help_text="Veces máximas que un maestro puede ganar el beneficio del plan (0 = Ilimitado)"
    )
    referral_eligible_user_type = models.CharField(
        max_length=20,
        choices=EligibleReferralUserType.choices,
        default=EligibleReferralUserType.ALL,
        verbose_name="Tipos de usuarios que suman a la meta",
        help_text="Define si suman a la meta registros de clientes, de maestros o ambos"
    )

    class Meta:
        verbose_name = "Configuración del Sistema"
        verbose_name_plural = "Configuración del Sistema"

    def __str__(self):
        return f"Configuración del Sistema (Suscripciones iOS: {'Activas' if self.subscriptions_enabled_ios else 'Inactivas'})"

    def is_subscription_enabled_for_version(self, platform='ios', app_version=None):
        """
        Determina si la sección de suscripciones y planes está habilitada
        para una plataforma y versión específica de la app.
        """
        platform = (platform or 'ios').lower()
        if platform == 'ios':
            is_enabled = self.subscriptions_enabled_ios
            min_v = (self.subscriptions_min_version_ios or '').strip()
            blocked_str = self.subscriptions_blocked_versions_ios or ''
        else:
            is_enabled = self.subscriptions_enabled_android
            min_v = (self.subscriptions_min_version_android or '').strip()
            blocked_str = self.subscriptions_blocked_versions_android or ''

        # Si el switch maestro de la plataforma está apagado, se bloquea para todas las versiones
        if not is_enabled:
            return False

        # Si no se indica versión, respetar el switch maestro
        if not app_version:
            return is_enabled

        raw_version = str(app_version).strip()
        clean_version = raw_version.split('+')[0].split('-')[0].strip()

        # 1. Verificar si está en la lista de versiones bloqueadas (ej: "1.0.6, 1.0.7")
        blocked_list = [b.strip() for b in blocked_str.split(',') if b.strip()]
        for blocked_item in blocked_list:
            clean_blocked = blocked_item.split('+')[0].split('-')[0].strip()
            if raw_version == blocked_item or clean_version == clean_blocked:
                return False

        # 2. Verificar versión mínima si está configurada
        if min_v:
            def parse_ver(v):
                try:
                    c = v.split('+')[0].split('-')[0].strip()
                    parts = [int(p) for p in c.split('.') if p.isdigit()]
                    while len(parts) < 3:
                        parts.append(0)
                    return parts[:3]
                except Exception:
                    return [0, 0, 0]

            if parse_ver(clean_version) < parse_ver(min_v):
                return False

        return True

    @classmethod
    def get_settings(cls):
        setting = cls.objects.first()
        if not setting:
            setting = cls.objects.create()
        return setting

    @classmethod
    def get_max_specialties(cls):
        return cls.get_settings().max_specialties_per_tradesman

    @classmethod
    def is_nationwide_coverage_active(cls):
        from django.conf import settings
        try:
            setting = cls.get_settings()
            db_active = getattr(setting, 'nationwide_coverage_mode', False)
        except Exception:
            db_active = False
        return db_active or getattr(settings, 'NATIONWIDE_COVERAGE_MODE', False)


class AssociateReferral(models.Model):
    """
    Registro de usuarios que se inscriben utilizando el código de asociado de un maestro.
    """
    referrer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="referrals_made",
        verbose_name="Maestro que refirió"
    )
    referred_user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="referred_by_relation",
        verbose_name="Usuario inscrito con el código"
    )
    referral_code_used = models.CharField(
        max_length=50,
        verbose_name="Código de asociado utilizado"
    )
    reward_granted = models.BooleanField(
        default=False,
        verbose_name="¿Premio ya otorgado?",
        help_text="Indica si este registro ya fue contabilizado en una meta N cumplida"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de inscripción"
    )

    class Meta:
        verbose_name = "Asociado Referido"
        verbose_name_plural = "Asociados Referidos"
        ordering = ['-created_at']

    def __str__(self):
        referrer_name = self.referrer.get_full_name() or self.referrer.username
        referred_name = self.referred_user.get_full_name() or self.referred_user.username
        return f"{referred_name} se inscribió con código de {referrer_name}"


class ReferralRewardLog(models.Model):
    """
    Historial de beneficios otorgados a los maestros por alcanzar metas de asociados.
    """
    professional = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="referral_rewards",
        verbose_name="Maestro beneficiado"
    )
    plan = models.ForeignKey(
        'users.SubscriptionPlan',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Plan otorgado"
    )
    days_granted = models.PositiveIntegerField(
        verbose_name="Días otorgados"
    )
    referrals_count_at_time = models.PositiveIntegerField(
        verbose_name="Inscritos acumulados a la fecha"
    )
    new_plan_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Nueva fecha de vencimiento"
    )
    granted_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de otorgamiento"
    )

    class Meta:
        verbose_name = "Historial de Beneficio por Asociados"
        verbose_name_plural = "Historial de Beneficios por Asociados"
        ordering = ['-granted_at']

    def __str__(self):
        prof_name = self.professional.get_full_name() or self.professional.username
        plan_name = self.plan.name if self.plan else 'Plan'
        return f"{prof_name} - {self.days_granted} días de {plan_name}"



class ReferralProgramContent(models.Model):
    """
    Textos configurables y localizados por idioma para el Programa de Asociados (Referidos).
    Permite a la gerencia modificar textos, mensajes de compartir, pasos y notificaciones.
    """
    class Language(models.TextChoices):
        SPANISH = 'es', 'Español'
        ENGLISH = 'en', 'English'
        FRENCH = 'fr', 'Français'

    language = models.CharField(
        max_length=10,
        choices=Language.choices,
        unique=True,
        default=Language.SPANISH,
        verbose_name="Idioma",
        help_text="Código de idioma (es, en, fr)"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Indica si esta versión de textos está disponible"
    )

    # Pantalla Principal del Código de Asociado
    hero_title = models.CharField(
        max_length=200,
        default="¡Invita y gana beneficios!",
        verbose_name="Título principal",
        help_text="Título en la cabecera de la pantalla de asociados"
    )
    hero_description = models.TextField(
        default="Comparte tu código con clientes o conocidos. Cada vez que {target} personas se inscriban con tu código, ganarás {days} días de {plan} gratis.",
        verbose_name="Descripción del beneficio",
        help_text="Variables disponibles: {target} (meta), {days} (días), {plan} (nombre del plan)"
    )
    share_message = models.TextField(
        default="¡Hola! Te invito a unirte a Clanship. Regístrate usando mi código de asociado {code} para contactarme y encontrar los mejores especialistas: https://clanship.cl",
        verbose_name="Mensaje para compartir (WhatsApp/Redes)",
        help_text="Variable disponible: {code} (código único del maestro)"
    )

    # Sección Informativa: ¿Cómo funciona?
    how_it_works_title = models.CharField(
        max_length=100,
        default="¿Cómo funciona?",
        verbose_name="Título: ¿Cómo funciona?"
    )
    step_1 = models.CharField(
        max_length=300,
        default="Comparte tu código con clientes o colegas.",
        verbose_name="Paso 1"
    )
    step_2 = models.CharField(
        max_length=300,
        default="Al registrarse en Clanship, ingresan tu código.",
        verbose_name="Paso 2"
    )
    step_3 = models.CharField(
        max_length=300,
        default="Al completar {target} asociados, ganas automáticamente {days} días de {plan}.",
        verbose_name="Paso 3",
        help_text="Variables disponibles: {target}, {days}, {plan}"
    )

    # Banners en Perfil y Mi Plan
    banner_title = models.CharField(
        max_length=100,
        default="Mi Código de Asociado",
        verbose_name="Título de banner en perfil"
    )
    banner_subtitle = models.CharField(
        max_length=200,
        default="Invita {target} asociados y gana un plan gratis",
        verbose_name="Subtítulo de banner en perfil",
        help_text="Variables disponibles: {target}, {days}, {plan}"
    )
    my_plan_invite_text = models.CharField(
        max_length=200,
        default="Invita {target} asociados y gana {days} días gratis de {plan}.",
        verbose_name="Texto de invitación en Mi Plan",
        help_text="Variables disponibles: {target}, {days}, {plan}"
    )
    active_benefit_text = models.CharField(
        max_length=200,
        default="Beneficio de plan activo hasta el {date}",
        verbose_name="Texto de beneficio activo",
        help_text="Variable disponible: {date}"
    )

    # Notificaciones (Push FCM y WebSocket)
    notification_new_referral = models.CharField(
        max_length=300,
        default="¡{name} se inscribió con tu código de asociado! Llevas {pending} de {target} para tu beneficio.",
        verbose_name="Notificación: Nuevo asociado inscrito",
        help_text="Variables disponibles: {name}, {pending}, {target}"
    )
    notification_reward_earned = models.CharField(
        max_length=300,
        default="¡Felicidades! Completaste tu meta de {target} asociados. Ganaste {days} días de {plan} gratis.",
        verbose_name="Notificación: Meta alcanzada (Beneficio ganado)",
        help_text="Variables disponibles: {target}, {days}, {plan}"
    )

    # Formulario de Registro
    registration_code_label = models.CharField(
        max_length=200,
        default="Código de asociado o invitación (Opcional)",
        verbose_name="Etiqueta de campo en registro"
    )
    registration_code_hint = models.CharField(
        max_length=100,
        default="Ej: CLAN-ABC12",
        verbose_name="Texto de ayuda / Placeholder en registro"
    )

    updated_at = models.DateTimeField(auto_now=True, verbose_name="Última modificación")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de creación")

    class Meta:
        verbose_name = "Contenido de Programa de Asociados"
        verbose_name_plural = "Contenidos de Programa de Asociados (por Idioma)"
        ordering = ['language']

    def __str__(self):
        return f"Contenido Asociados ({self.get_language_display()})"

    @classmethod
    def get_content_for_language(cls, lang_code=None):
        if lang_code:
            lang_code = lang_code.split('-')[0].split('_')[0].lower()
        else:
            lang_code = 'es'
        
        content = cls.objects.filter(language=lang_code, is_active=True).first()
        if content:
            return content
        
        if lang_code != 'es':
            spanish = cls.objects.filter(language='es', is_active=True).first()
            if spanish:
                return spanish
        
        return cls(language='es')



class AppVersionConfig(models.Model):
    class AppType(models.TextChoices):
        CLIENT = 'CLIENT', 'Cliente'
        TRADESMAN = 'TRADESMAN', 'Especialista / Maestro'

    app_type = models.CharField(
        max_length=20, 
        choices=AppType.choices, 
        unique=True, 
        verbose_name="Aplicación"
    )
    min_version = models.CharField(
        max_length=20, 
        default='1.0.0', 
        verbose_name="Versión Mínima Obligatoria",
        help_text="Versiones inferiores a esta serán bloqueadas en el inicio de la app."
    )
    latest_version = models.CharField(
        max_length=20, 
        default='1.0.0', 
        verbose_name="Última Versión Disponible",
        help_text="Versión recomendada en las tiendas."
    )
    store_url_android = models.URLField(
        verbose_name="URL Play Store (Android)",
        blank=True, null=True
    )
    store_url_ios = models.URLField(
        verbose_name="URL App Store (iOS)",
        blank=True, null=True
    )
    title = models.CharField(
        max_length=100, 
        default='Actualización Requerida', 
        verbose_name="Título del Diálogo"
    )
    message = models.TextField(
        default='Para continuar usando Clanship de manera segura, por favor actualiza la aplicación a la última versión disponible.',
        verbose_name="Mensaje de Bloqueo"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Control de Versión Activo"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración de Versión de App"
        verbose_name_plural = "Configuración de Versiones de Apps"

    def __str__(self):
        return f"{self.get_app_type_display()} - Mínima: {self.min_version} | Última: {self.latest_version}"


from django.db.models.signals import m2m_changed
from django.core.exceptions import ValidationError
from django.dispatch import receiver

@receiver(m2m_changed, sender=ProfessionalProfile.subtags.through)
def limit_subtags_and_sync_tags(sender, instance, action, **kwargs):
    if action in ["post_add", "post_remove", "post_clear"]:
        parent_tag_ids = list(instance.subtags.values_list('tag_id', flat=True).distinct())
        if parent_tag_ids:
            instance.tags.add(*parent_tag_ids)
            parent_specialty_ids = list(Tag.objects.filter(id__in=parent_tag_ids, specialty_id__isnull=False).values_list('specialty_id', flat=True).distinct())
            if parent_specialty_ids:
                instance.specialties.add(*parent_specialty_ids)
                if not instance.specialty_id:
                    instance.specialty_id = parent_specialty_ids[0]
                    instance.save(update_fields=['specialty'])

@receiver(m2m_changed, sender=ProfessionalProfile.tags.through)
def sync_specialties_from_tags(sender, instance, action, **kwargs):
    if action in ["post_add", "post_remove", "post_clear"]:
        tag_ids = list(instance.tags.values_list('id', flat=True).distinct())
        if tag_ids:
            parent_specialty_ids = list(Tag.objects.filter(id__in=tag_ids, specialty_id__isnull=False).values_list('specialty_id', flat=True).distinct())
            if parent_specialty_ids:
                instance.specialties.add(*parent_specialty_ids)
                if not instance.specialty_id:
                    instance.specialty_id = parent_specialty_ids[0]
                    instance.save(update_fields=['specialty'])


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


class UserReport(models.Model):
    reporter = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='reports_made',
        verbose_name="Usuario que reporta"
    )
    reported_user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='reports_received',
        verbose_name="Usuario reportado"
    )
    reason = models.TextField(verbose_name="Motivo del reporte")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de reporte")
    is_resolved = models.BooleanField(default=False, verbose_name="¿Resuelto?")
    
    class Meta:
        verbose_name = "Reporte de Usuario"
        verbose_name_plural = "Reportes de Usuarios"
        
    def __str__(self):
        reporter_name = getattr(self.reporter, 'username', 'Desconocido')
        reported_name = getattr(self.reported_user, 'username', 'Desconocido')
        return f"Reporte de {reporter_name} hacia {reported_name}"


class SeasonalCampaign(models.Model):
    """
    Configuración remota de temporadas y festividades (Remote Theming & Banners).
    Permite activar paletas de colores, insignias sobre el logo, banners promocionales
    y micro-efectos festivos desde Django Admin sin recompilar la app móvil.
    """
    class SeasonType(models.TextChoices):
        FIESTAS_PATRIAS = 'FIESTAS_PATRIAS', 'Fiestas Patrias (18 de Septiembre)'
        HALLOWEEN = 'HALLOWEEN', 'Halloween'
        NAVIDAD = 'NAVIDAD', 'Navidad y Fin de Año'
        VERANO = 'VERANO', 'Verano'
        CYBER = 'CYBER', 'CyberDays / Descuentos'
        CUSTOM = 'CUSTOM', 'Personalizada'

    class AppType(models.TextChoices):
        ALL = 'ALL', 'Todas las aplicaciones'
        CLIENT = 'CLIENT', 'Cliente'
        TRADESMAN = 'TRADESMAN', 'Especialista / Maestro'

    class ParticleEffect(models.TextChoices):
        NONE = 'NONE', 'Ninguno'
        CONFETTI = 'CONFETTI', 'Confeti / Challa (Fiestas Patrias / Año Nuevo)'
        SNOW = 'SNOW', 'Nieve (Navidad)'
        STARS = 'STARS', 'Estrellas / Destellos'

    class ActionType(models.TextChoices):
        REQUEST_JOB = 'REQUEST_JOB', 'Abrir creación de solicitud'
        SEARCH_TAG = 'SEARCH_TAG', 'Filtrar por etiqueta / especialidad'
        DEEP_LINK = 'DEEP_LINK', 'Abrir enlace externo / WebView'

    name = models.CharField(max_length=100, verbose_name="Nombre de la campaña", help_text="Ej: Fiestas Patrias 2026")
    season_type = models.CharField(max_length=30, choices=SeasonType.choices, default=SeasonType.CUSTOM, verbose_name="Festividad / Tipo")
    app_type = models.CharField(max_length=20, choices=AppType.choices, default=AppType.CLIENT, verbose_name="Aplicación de destino")
    is_active = models.BooleanField(default=True, verbose_name="¿Activa?", help_text="Interruptor maestro (Kill switch) para encender o apagar de inmediato.")
    
    start_date = models.DateTimeField(verbose_name="Fecha y hora de inicio")
    end_date = models.DateTimeField(verbose_name="Fecha y hora de término")
    priority = models.PositiveIntegerField(default=1, verbose_name="Prioridad", help_text="Mayor valor tiene precedencia si dos campañas se solapan en fechas.")

    # Paleta de colores temáticos (Overrides opcionales)
    primary_color = models.CharField(max_length=9, blank=True, null=True, verbose_name="Color primario", help_text="Hexadecimal ej: #0B6E4F")
    secondary_color = models.CharField(max_length=9, blank=True, null=True, verbose_name="Color secundario", help_text="Hexadecimal ej: #0D2B45")
    accent_color = models.CharField(max_length=9, blank=True, null=True, verbose_name="Color de acento", help_text="Hexadecimal ej: #D52B1E o #FF7518")
    header_gradient_start = models.CharField(max_length=9, blank=True, null=True, verbose_name="Inicio gradiente cabecera", help_text="Hexadecimal ej: #0D2B45")
    header_gradient_end = models.CharField(max_length=9, blank=True, null=True, verbose_name="Fin gradiente cabecera", help_text="Hexadecimal ej: #163E63")
    search_bar_border_color = models.CharField(max_length=9, blank=True, null=True, verbose_name="Color borde buscador Home", help_text="Hexadecimal ej: #D52B1E. Si está vacío, usa el color de acento.")
    nav_center_color = models.CharField(max_length=9, blank=True, null=True, verbose_name="Color botón central del menú", help_text="Hexadecimal ej: #D52B1E. Si está vacío, usa el color primario.")
    stat_cards_bg_color = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        verbose_name="Color fondo cuadros (General / Fallback)",
        help_text="Hexadecimal ej: #F1F5F9. Aplica a todas las tarjetas de solicitudes que no tengan un color específico."
    )
    stat_card_active_bg_color = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        verbose_name="Color fondo: Solicitudes de Trabajo (Activas)",
        help_text="Hexadecimal ej: #F1F5F9 o #0D2B45."
    )
    stat_card_completed_bg_color = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        verbose_name="Color fondo: Solicitudes Completadas",
        help_text="Hexadecimal ej: #ECFDF5 (verde menta suave)."
    )
    stat_card_rejected_bg_color = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        verbose_name="Color fondo: Solicitudes Rechazadas",
        help_text="Hexadecimal ej: #FEF2F2 (rojo suave)."
    )
    stat_card_scheduled_bg_color = models.CharField(
        max_length=9,
        blank=True,
        null=True,
        verbose_name="Color fondo: Solicitudes Programadas",
        help_text="Hexadecimal ej: #FFFBEB (ámbar suave)."
    )

    # Personalización de textos, números e iconos en tarjetas (Tradesman)
    stat_cards_number_color = models.CharField(
        max_length=9, blank=True, null=True,
        verbose_name="Color números tarjetas (General / Fallback)",
        help_text="Hexadecimal ej: #0B6E4F para el número grande de las tarjetas."
    )
    stat_cards_text_color = models.CharField(
        max_length=9, blank=True, null=True,
        verbose_name="Color textos tarjetas (General / Fallback)",
        help_text="Hexadecimal ej: #2E3135 para la etiqueta de las tarjetas."
    )
    stat_cards_icon_color = models.CharField(
        max_length=9, blank=True, null=True,
        verbose_name="Color iconos tarjetas (General / Fallback)",
        help_text="Hexadecimal ej: #0B6E4F para el icono y halo de las tarjetas."
    )

    stat_card_active_number_color = models.CharField(
        max_length=9, blank=True, null=True,
        verbose_name="Color número: Solicitudes de Trabajo",
        help_text="Hexadecimal ej: #2E3135 o #0D2B45."
    )
    stat_card_active_text_color = models.CharField(
        max_length=9, blank=True, null=True,
        verbose_name="Color texto: Solicitudes de Trabajo",
        help_text="Hexadecimal ej: #2E3135."
    )
    stat_card_active_icon_color = models.CharField(
        max_length=9, blank=True, null=True,
        verbose_name="Color icono: Solicitudes de Trabajo",
        help_text="Hexadecimal ej: #2E3135."
    )

    stat_card_completed_number_color = models.CharField(
        max_length=9, blank=True, null=True,
        verbose_name="Color número: Solicitudes Completadas",
        help_text="Hexadecimal ej: #0B6E4F."
    )
    stat_card_completed_text_color = models.CharField(
        max_length=9, blank=True, null=True,
        verbose_name="Color texto: Solicitudes Completadas",
        help_text="Hexadecimal ej: #2E3135."
    )
    stat_card_completed_icon_color = models.CharField(
        max_length=9, blank=True, null=True,
        verbose_name="Color icono: Solicitudes Completadas",
        help_text="Hexadecimal ej: #0B6E4F."
    )

    stat_card_rejected_number_color = models.CharField(
        max_length=9, blank=True, null=True,
        verbose_name="Color número: Solicitudes Rechazadas",
        help_text="Hexadecimal ej: #EA4335."
    )
    stat_card_rejected_text_color = models.CharField(
        max_length=9, blank=True, null=True,
        verbose_name="Color texto: Solicitudes Rechazadas",
        help_text="Hexadecimal ej: #2E3135."
    )
    stat_card_rejected_icon_color = models.CharField(
        max_length=9, blank=True, null=True,
        verbose_name="Color icono: Solicitudes Rechazadas",
        help_text="Hexadecimal ej: #EA4335."
    )

    stat_card_scheduled_number_color = models.CharField(
        max_length=9, blank=True, null=True,
        verbose_name="Color número: Solicitudes Programadas",
        help_text="Hexadecimal ej: #F28C28."
    )
    stat_card_scheduled_text_color = models.CharField(
        max_length=9, blank=True, null=True,
        verbose_name="Color texto: Solicitudes Programadas",
        help_text="Hexadecimal ej: #2E3135."
    )
    stat_card_scheduled_icon_color = models.CharField(
        max_length=9, blank=True, null=True,
        verbose_name="Color icono: Solicitudes Programadas",
        help_text="Hexadecimal ej: #F28C28."
    )

    # Assets visuales y animaciones
    logo_badge_icon = models.FileField(upload_to="seasonal/badges/", blank=True, null=True, verbose_name="Insignia para logo/avatar", help_text="PNG transparente o SVG (chupalla, gorro navideño, calabaza)")
    nav_center_icon = models.FileField(upload_to="seasonal/nav_icons/", blank=True, null=True, verbose_name="Icono central de navegación (PNG)", help_text="PNG transparente para reemplazar el icono de explorar/mapa en el menú inferior")
    banner_image = models.ImageField(upload_to="seasonal/banners/", blank=True, null=True, verbose_name="Imagen de banner de fondo", help_text="Imagen opcional para el banner principal")
    stat_cards_bg_image = models.ImageField(
        upload_to="seasonal/stat_cards/",
        blank=True,
        null=True,
        verbose_name="Imagen de fondo cuadros (General / Fallback)",
        help_text="Imagen para las tarjetas que no tengan una imagen específica."
    )
    stat_card_active_bg_image = models.ImageField(
        upload_to="seasonal/stat_cards/",
        blank=True,
        null=True,
        verbose_name="Imagen fondo: Solicitudes de Trabajo (Activas)",
        help_text="Imagen específica para la tarjeta de Solicitudes de Trabajo."
    )
    stat_card_completed_bg_image = models.ImageField(
        upload_to="seasonal/stat_cards/",
        blank=True,
        null=True,
        verbose_name="Imagen fondo: Solicitudes Completadas",
        help_text="Imagen específica para la tarjeta de Solicitudes Completadas."
    )
    stat_card_rejected_bg_image = models.ImageField(
        upload_to="seasonal/stat_cards/",
        blank=True,
        null=True,
        verbose_name="Imagen fondo: Solicitudes Rechazadas",
        help_text="Imagen específica para la tarjeta de Solicitudes Rechazadas."
    )
    stat_card_scheduled_bg_image = models.ImageField(
        upload_to="seasonal/stat_cards/",
        blank=True,
        null=True,
        verbose_name="Imagen fondo: Solicitudes Programadas",
        help_text="Imagen específica para la tarjeta de Solicitudes Programadas."
    )
    stat_cards_image_opacity = models.PositiveSmallIntegerField(
        blank=True, null=True,
        verbose_name="Opacidad imagen tarjetas - General (%)",
        help_text="Porcentaje de 0 a 100% (ej: 25 para marca de agua sutil, 75 para imagen visible, 100 para foto completa sin filtro). Aplica a las que no definan un porcentaje propio."
    )
    stat_card_active_image_opacity = models.PositiveSmallIntegerField(
        blank=True, null=True,
        verbose_name="Opacidad imagen: Solicitudes de Trabajo (%)",
        help_text="0 a 100% de visibilidad."
    )
    stat_card_completed_image_opacity = models.PositiveSmallIntegerField(
        blank=True, null=True,
        verbose_name="Opacidad imagen: Solicitudes Completadas (%)",
        help_text="0 a 100% de visibilidad."
    )
    stat_card_rejected_image_opacity = models.PositiveSmallIntegerField(
        blank=True, null=True,
        verbose_name="Opacidad imagen: Solicitudes Rechazadas (%)",
        help_text="0 a 100% de visibilidad."
    )
    stat_card_scheduled_image_opacity = models.PositiveSmallIntegerField(
        blank=True, null=True,
        verbose_name="Opacidad imagen: Solicitudes Programadas (%)",
        help_text="0 a 100% de visibilidad."
    )
    class GarlandPosition(models.TextChoices):
        BOTH = 'BOTH', 'En ambos (Barra superior y Card principal)'
        TOP = 'TOP', 'Solo arriba (Barra superior / Nombre)'
        BOTTOM = 'BOTTOM', 'Solo abajo (Card principal / Banner)'

    show_top_garland = models.BooleanField(default=False, verbose_name="¿Mostrar guirnaldas / banderines?", help_text="Activa la fila decorativa de guirnaldas (Banderas chilenas, Murciélagos o Guirnalda de pino).")
    garland_position = models.CharField(
        max_length=20,
        choices=GarlandPosition.choices,
        default=GarlandPosition.BOTH,
        verbose_name="Ubicación de guirnaldas",
        help_text="Controla si las guirnaldas aparecen arriba (en la barra superior), abajo (en el card principal), o en ambos lugares."
    )
    custom_garland_image = models.FileField(upload_to="seasonal/garlands/", blank=True, null=True, verbose_name="Imagen de guirnalda personalizada (PNG)", help_text="Opcional: PNG transparente que reemplaza la guirnalda automática.")
    particle_effect = models.CharField(max_length=20, choices=ParticleEffect.choices, default=ParticleEffect.NONE, verbose_name="Efecto de partículas")

    # Textos y mensajes dinámicos
    greeting_prefix = models.CharField(max_length=60, blank=True, null=True, verbose_name="Prefijo de saludo", help_text="Ej: '¡Tikitikiti!', '¡Feliz Navidad!', '¡Feliz 18!'")
    promo_banner_title = models.CharField(max_length=120, blank=True, null=True, verbose_name="Título del banner", help_text="Ej: ¡Celebra el 18 sin preocupaciones!")
    promo_banner_subtitle = models.CharField(max_length=220, blank=True, null=True, verbose_name="Subtítulo del banner", help_text="Ej: Parrilleros, gasfitería y electricidad para tu fonda o casa.")
    promo_banner_cta_text = models.CharField(max_length=50, blank=True, null=True, verbose_name="Texto botón acción (CTA)", help_text="Ej: Pedir Especialista")
    promo_banner_action_type = models.CharField(max_length=20, choices=ActionType.choices, default=ActionType.REQUEST_JOB, verbose_name="Tipo de acción")
    promo_banner_action_value = models.CharField(max_length=200, blank=True, null=True, verbose_name="Valor de acción", help_text="Nombre de especialidad a buscar o URL externa")

    # Etiquetas destacadas de temporada
    featured_tags = models.ManyToManyField('users.Tag', blank=True, related_name="seasonal_campaigns", verbose_name="Etiquetas destacadas")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Campaña de Temporada / Festividad"
        verbose_name_plural = "Campañas de Temporada / Festividades"
        ordering = ['-priority', '-start_date']

    def __str__(self):
        return f"{self.name} ({self.get_season_type_display()})"

    @property
    def is_currently_live(self):
        now = timezone.now()
        return self.is_active and (self.start_date <= now <= self.end_date)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._optimize_images()

    def _optimize_images(self):
        """
        Comprime y redimensiona imágenes subidas para garantizar carga instantánea en móviles.
        """
        import os
        import io
        from PIL import Image

        image_fields = [
            'stat_cards_bg_image',
            'stat_card_active_bg_image',
            'stat_card_completed_bg_image',
            'stat_card_rejected_bg_image',
            'stat_card_scheduled_bg_image',
            'banner_image',
        ]
        for field_name in image_fields:
            image_field = getattr(self, field_name)
            if image_field and hasattr(image_field, 'path') and os.path.exists(image_field.path):
                try:
                    file_size = os.path.getsize(image_field.path)
                    if file_size > 120 * 1024:  # Si supera 120KB, optimizar
                        with Image.open(image_field.path) as img:
                            img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                            buffer = io.BytesIO()
                            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                                img.save(buffer, format='PNG', optimize=True)
                            else:
                                img.convert('RGB').save(buffer, format='JPEG', quality=85, optimize=True)
                            with open(image_field.path, 'wb') as f:
                                f.write(buffer.getvalue())
                except Exception:
                    pass

