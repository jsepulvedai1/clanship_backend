import json
import logging
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .services import process_mercadopago_payment
from .models import PlanSubscriptionOrder

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def mercadopago_webhook(request):
    """
    Receptor de Webhooks / Notificaciones IPN de Mercado Pago.
    Procesa notificaciones de pagos de suscripciones.
    """
    if request.method == "GET":
        # Health check o ping de verificación de Mercado Pago
        return JsonResponse({"status": "active", "service": "clanship-mercadopago-webhook"})

    try:
        raw_body = request.body.decode('utf-8') if request.body else "{}"
        payload = json.loads(raw_body) if raw_body else {}
    except Exception:
        payload = {}

    topic = request.GET.get("topic") or request.GET.get("type") or payload.get("type")
    data_id = (
        request.GET.get("id") or 
        request.GET.get("data.id") or 
        payload.get("data", {}).get("id")
    )

    logger.info(f"Webhook Mercado Pago recibido: topic={topic}, id={data_id}")

    # Mercado Pago envía 'payment' para cobros estándar y Checkout Pro
    if topic == "payment" and data_id:
        try:
            order = process_mercadopago_payment(data_id, raw_payload=payload)
            if order:
                logger.info(f"Orden {order.external_reference} procesada. Estado: {order.status}")
        except Exception as e:
            logger.error(f"Error procesando pago {data_id}: {str(e)}", exc_info=True)
            # Retornamos 200 para evitar que Mercado Pago reintente infinitamente si es un error lógico
            return JsonResponse({"status": "error_handled", "message": str(e)}, status=200)

    return JsonResponse({"status": "received"}, status=200)


def payment_success_view(request):
    """Página de retorno tras pago aprobado en Mercado Pago."""
    ref = request.GET.get("ref", "")
    plan_name = "tu plan"
    if ref:
        order = PlanSubscriptionOrder.objects.filter(external_reference=ref).select_related('plan').first()
        if order:
            plan_name = order.plan.name

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pago Exitoso - Clanship Maestro</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; text-align: center; padding: 40px 20px; background: #0b132b; color: #ffffff; }}
            .card {{ max-width: 420px; margin: auto; background: #1c2541; padding: 32px; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
            .icon {{ font-size: 64px; color: #4ade80; margin-bottom: 16px; }}
            h1 {{ font-size: 24px; margin-bottom: 8px; color: #ffffff; }}
            p {{ color: #94a3b8; font-size: 15px; line-height: 1.5; }}
            .badge {{ background: rgba(74, 222, 128, 0.2); color: #4ade80; padding: 6px 14px; border-radius: 20px; font-weight: bold; display: inline-block; margin-top: 10px; }}
            .btn {{ display: inline-block; margin-top: 24px; padding: 12px 24px; background: #0077b6; color: white; text-decoration: none; border-radius: 12px; font-weight: bold; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">✓</div>
            <h1>¡Pago Confirmado!</h1>
            <p>La suscripción a <strong>{plan_name}</strong> se ha activado exitosamente en tu cuenta de maestro.</p>
            <div class="badge">Plan Activo</div>
            <br>
            <p style="margin-top: 20px; font-size: 13px;">Ya puedes cerrar esta ventana y regresar a la app Clanship Maestro.</p>
        </div>
    </body>
    </html>
    """
    return HttpResponse(html)


def payment_failure_view(request):
    """Página de retorno si el pago fue cancelado o rechazado."""
    html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pago No Completado - Clanship</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; text-align: center; padding: 40px 20px; background: #0b132b; color: #ffffff; }
            .card { max-width: 420px; margin: auto; background: #1c2541; padding: 32px; border-radius: 20px; }
            .icon { font-size: 64px; color: #f87171; margin-bottom: 16px; }
            h1 { font-size: 22px; color: #ffffff; }
            p { color: #94a3b8; font-size: 15px; }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">✕</div>
            <h1>Pago no completado</h1>
            <p>El proceso de pago fue cancelado o rechazado por el medio de pago. Puedes volver a intentarlo desde la app Clanship Maestro.</p>
        </div>
    </body>
    </html>
    """
    return HttpResponse(html)


def payment_pending_view(request):
    """Página de retorno si el pago quedó en espera de acreditación."""
    html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pago Pendiente - Clanship</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; text-align: center; padding: 40px 20px; background: #0b132b; color: #ffffff; }
            .card { max-width: 420px; margin: auto; background: #1c2541; padding: 32px; border-radius: 20px; }
            .icon { font-size: 64px; color: #facc15; margin-bottom: 16px; }
            h1 { font-size: 22px; color: #ffffff; }
            p { color: #94a3b8; font-size: 15px; }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">⏳</div>
            <h1>Pago en proceso</h1>
            <p>Tu pago está siendo procesado por la entidad bancaria. En cuanto se confirme, tu plan se activará automáticamente.</p>
        </div>
    </body>
    </html>
    """
    return HttpResponse(html)
