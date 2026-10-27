import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class PlanSubscriptionOrder(models.Model):
    """
    Registro y seguimiento de órdenes de compra/suscripción de planes por parte de maestros.
    """
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente'
        APPROVED = 'APPROVED', 'Aprobado / Pagado'
        REJECTED = 'REJECTED', 'Rechazado'
        CANCELLED = 'CANCELLED', 'Cancelado'
        REFUNDED = 'REFUNDED', 'Reembolsado'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='plan_subscription_orders',
        verbose_name='Maestro / Profesional'
    )
    plan = models.ForeignKey(
        'users.SubscriptionPlan',
        on_delete=models.PROTECT,
        related_name='subscription_orders',
        verbose_name='Plan de Suscripción'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Monto (CLP)'
    )
    currency = models.CharField(
        max_length=5,
        default='CLP',
        verbose_name='Moneda'
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        verbose_name='Estado del Pago'
    )
    external_reference = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name='Referencia Externa (Mercado Pago)'
    )
    preference_id = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name='ID de Preferencia MP'
    )
    init_point = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='URL de Pago Producción'
    )
    sandbox_init_point = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name='URL de Pago Sandbox'
    )
    mp_payment_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        verbose_name='ID de Pago Mercado Pago'
    )
    payment_method_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Método de Pago (ej. webpay, visa)'
    )
    payment_type_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name='Tipo de Pago (ej. credit_card, debit_card)'
    )
    raw_webhook_data = models.JSONField(
        blank=True,
        null=True,
        verbose_name='Payload Webhook Recibido'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de Creación'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Última Actualización'
    )
    paid_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name='Fecha de Pago Aprobado'
    )

    class Meta:
        verbose_name = 'Orden de Suscripción'
        verbose_name_plural = 'Órdenes de Suscripción'
        ordering = ['-created_at']

    def __str__(self):
        return f"Orden #{self.external_reference} - {self.user.get_full_name() or self.user.username} ({self.plan.name}) - {self.get_status_display()}"
