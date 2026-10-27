import logging
import mercadopago
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import PlanSubscriptionOrder

logger = logging.getLogger(__name__)


def get_mercadopago_sdk():
    """Retorna una instancia configurada del SDK oficial de Mercado Pago."""
    access_token = getattr(settings, 'MERCADOPAGO_ACCESS_TOKEN', '')
    if not access_token:
        raise ValueError("MERCADOPAGO_ACCESS_TOKEN no está configurado en settings.")
    return mercadopago.SDK(access_token)


def create_plan_subscription_preference(user, plan, base_return_url=None):
    """
    Crea una preferencia de pago en Mercado Pago para la suscripción a un plan.
    Registra una orden pendiente en base de datos.
    """
    sdk = get_mercadopago_sdk()
    
    # Base URL para redirecciones y webhooks
    backend_base_url = getattr(settings, 'BACKEND_BASE_URL', 'https://api.clanship.cl').rstrip('/')
    return_base = (base_return_url or backend_base_url).rstrip('/')

    # Generar referencia externa única
    timestamp = int(timezone.now().timestamp())
    external_ref = f"CLAN-PLAN-{plan.id}-{user.id}-{timestamp}"

    # Crear orden de suscripción en estado PENDING
    order = PlanSubscriptionOrder.objects.create(
        user=user,
        plan=plan,
        amount=plan.price,
        currency=getattr(settings, 'MERCADOPAGO_CURRENCY', 'CLP'),
        status=PlanSubscriptionOrder.Status.PENDING,
        external_reference=external_ref
    )

    webhook_url = f"{backend_base_url}/api/payments/mercadopago/webhook/"

    preference_data = {
        "items": [
            {
                "id": str(plan.id),
                "title": f"Suscripción Clanship: Plan {plan.name}",
                "description": plan.description or f"Acceso profesional a Clanship ({plan.duration_days} días)",
                "quantity": 1,
                "currency_id": getattr(settings, 'MERCADOPAGO_CURRENCY', 'CLP'),
                "unit_price": int(plan.price),  # En CLP debe ser entero
            }
        ],
        "payer": {
            "name": user.first_name or "Maestro",
            "surname": user.last_name or "Clanship",
            "email": user.email,
        },
        "back_urls": {
            "success": f"{return_base}/api/payments/mercadopago/success/?ref={external_ref}",
            "failure": f"{return_base}/api/payments/mercadopago/failure/?ref={external_ref}",
            "pending": f"{return_base}/api/payments/mercadopago/pending/?ref={external_ref}",
        },
        "auto_return": "approved",
        "external_reference": external_ref,
        "notification_url": webhook_url,
    }

    logger.info(f"Creando preferencia MP para {user.email} con ref {external_ref}")
    preference_response = sdk.preference().create(preference_data)

    if preference_response.get("status") not in (200, 201):
        err = preference_response.get("response", {})
        logger.error(f"Error creando preferencia Mercado Pago: {err}")
        order.status = PlanSubscriptionOrder.Status.CANCELLED
        order.save(update_fields=['status'])
        raise Exception(f"Error en Mercado Pago: {err.get('message', 'No fue posible crear la preferencia de pago')}")

    resp = preference_response["response"]
    order.preference_id = resp.get("id")
    order.init_point = resp.get("init_point")
    order.sandbox_init_point = resp.get("sandbox_init_point")
    order.save(update_fields=['preference_id', 'init_point', 'sandbox_init_point'])

    # Si estamos en DEBUG usar sandbox_init_point, en producción init_point
    is_debug = getattr(settings, 'DEBUG', False)
    checkout_url = order.sandbox_init_point if is_debug and order.sandbox_init_point else order.init_point

    return {
        "order": order,
        "preference_id": order.preference_id,
        "checkout_url": checkout_url,
        "init_point": order.init_point,
        "sandbox_init_point": order.sandbox_init_point,
    }


def process_mercadopago_payment(payment_id, raw_payload=None):
    """
    Consulta a Mercado Pago por un ID de pago, valida el estado y activa el plan si fue aprobado.
    """
    sdk = get_mercadopago_sdk()
    logger.info(f"Consultando estado del pago MP: {payment_id}")
    
    payment_info = sdk.payment().get(str(payment_id))
    if payment_info.get("status") != 200:
        logger.error(f"No se pudo consultar el pago {payment_id} en MP: {payment_info}")
        return None

    payment_data = payment_info.get("response", {})
    external_ref = payment_data.get("external_reference")
    status_mp = payment_data.get("status")  # 'approved', 'pending', 'rejected', 'cancelled'

    if not external_ref:
        logger.warning(f"Pago MP {payment_id} sin external_reference. Ignorando.")
        return None

    try:
        order = PlanSubscriptionOrder.objects.select_related('user__professional_profile', 'plan').get(
            external_reference=external_ref
        )
    except PlanSubscriptionOrder.DoesNotExist:
        logger.warning(f"No existe orden con external_reference: {external_ref}")
        return None

    # Guardar detalles técnicos del pago
    order.mp_payment_id = str(payment_id)
    order.payment_method_id = payment_data.get("payment_method_id")
    order.payment_type_id = payment_data.get("payment_type_id")
    if raw_payload:
        order.raw_webhook_data = raw_payload

    if status_mp == 'approved':
        if order.status != PlanSubscriptionOrder.Status.APPROVED:
            order.status = PlanSubscriptionOrder.Status.APPROVED
            order.paid_at = timezone.now()
            order.save()

            # Activar el plan al perfil profesional
            user = order.user
            profile = getattr(user, 'professional_profile', None)
            if profile:
                profile.plan = order.plan
                profile.plan_start_date = timezone.now()
                # Extender vigencia según duration_days (default 30 días)
                duration = order.plan.duration_days or 30
                profile.plan_expires_at = timezone.now() + timedelta(days=duration)
                profile.save(update_fields=['plan', 'plan_start_date', 'plan_expires_at'])
                logger.info(f"Plan {order.plan.name} activado con éxito para usuario {user.email} hasta {profile.plan_expires_at}")
        else:
            order.save()
    elif status_mp in ('rejected', 'cancelled'):
        order.status = PlanSubscriptionOrder.Status.REJECTED if status_mp == 'rejected' else PlanSubscriptionOrder.Status.CANCELLED
        order.save()
    else:
        order.save()

    return order
