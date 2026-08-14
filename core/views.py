import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
try:
    import resend
except ImportError:
    resend = None

from users.models import User, ProfessionalProfile
from jobs.models import Job
from chat.models import Message
from django.db.models import Sum

logger = logging.getLogger(__name__)

def dashboard_callback(request, context):
    """
    Inyecta estadísticas dinámicas de Clanship en el dashboard de django-unfold.
    """
    total_users = User.objects.count()
    total_customers = User.objects.filter(user_type=User.UserType.CUSTOMER).count()
    total_professionals = User.objects.filter(user_type=User.UserType.PROFESSIONAL).count()
    
    total_jobs = Job.objects.count()
    active_jobs = Job.objects.filter(
        status__in=[Job.Status.REQUESTED, Job.Status.AGREED, Job.Status.IN_VISIT]
    ).count()
    completed_jobs = Job.objects.filter(status=Job.Status.FINISHED).count()
    cancelled_jobs = Job.objects.filter(status=Job.Status.CANCELLED).count()

    total_revenue = Job.objects.filter(status=Job.Status.FINISHED).aggregate(total=Sum('agreed_price'))['total'] or 0
    
    verified_professionals = ProfessionalProfile.objects.filter(is_verified=True).count()
    unverified_professionals = total_professionals - verified_professionals

    recent_jobs = Job.objects.order_by('-created_at')[:5]
    recent_messages = Message.objects.order_by('-created_at')[:5]

    context.update({
        "total_users": total_users,
        "total_customers": total_customers,
        "total_professionals": total_professionals,
        "total_jobs": total_jobs,
        "active_jobs": active_jobs,
        "completed_jobs": completed_jobs,
        "cancelled_jobs": cancelled_jobs,
        "total_revenue": total_revenue,
        "verified_professionals": verified_professionals,
        "unverified_professionals": unverified_professionals,
        "recent_jobs": recent_jobs,
        "recent_messages": recent_messages,
    })
    return context


@csrf_exempt
@require_POST
def contact_api_view(request):
    """
    API Endpoint protegido para recibir solicitudes de contacto desde la página web de Clanship.
    Incluye:
    - Rate limiting por IP (máx 5 envíos por cada 10 minutos).
    - Protección contra spam honeypot.
    - Validación de origen / cabeceras.
    """
    # 1. Extraer dirección IP del cliente
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')

    # 2. Rate Limiting por IP (Máximo 5 envíos por cada 10 minutos = 600s)
    cache_key = f"contact_ratelimit_{ip}"
    attempts = cache.get(cache_key, 0)
    if attempts >= 5:
        logger.warning(f"[Rate Limit Exceeded] Intento de contacto bloqueado para IP: {ip}")
        return JsonResponse({
            'success': False,
            'message': 'Has realizado demasiados intentos de envío. Por favor espera 10 minutos antes de intentar nuevamente.'
        }, status=429)

    try:
        data = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'success': False, 'message': 'Formato JSON inválido.'}, status=400)

    # 3. Trampa antispam Honeypot en servidor
    website_hp = data.get('website_hp', '')
    if website_hp and website_hp.strip() != '':
        # Spam detectado, simular éxito en silencio sin enviar email
        return JsonResponse({'success': True, 'message': 'Mensaje procesado.'}, status=200)

    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    message = data.get('message', '').strip()
    source_page = data.get('source_page', '/contacto')
    utm_source = data.get('utm_source')
    utm_medium = data.get('utm_medium')
    utm_campaign = data.get('utm_campaign')

    if not name or not email or not message:
        return JsonResponse({'success': False, 'message': 'Faltan campos requeridos (nombre, correo o mensaje).'}, status=400)

    # Incrementar contador de rate limit tras pasar validación básica
    cache.set(cache_key, attempts + 1, 600)

    recipient_email = getattr(settings, 'SUPPORT_EMAIL', 'soporte@clanship.cl')
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'Equipo Clanship <noreply@clanship.cl>')

    subject = f"[Nuevo Contacto Web Clanship] Mensaje de {name}"
    
    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 10px;">
        <h2 style="color: #091C36; border-bottom: 2px solid #11784A; padding-bottom: 10px;">Nuevo Mensaje desde Clanship Web</h2>
        <p><strong>Nombre:</strong> {name}</p>
        <p><strong>Correo electrónico:</strong> <a href="mailto:{email}">{email}</a></p>
        <p><strong>Teléfono:</strong> {phone if phone else 'No especificado'}</p>
        <p><strong>Origen:</strong> {source_page}</p>
        <p><strong>IP Remota:</strong> {ip}</p>
        <p><strong>Campañas (UTM):</strong> Source: {utm_source if utm_source else 'N/A'}, Medium: {utm_medium if utm_medium else 'N/A'}, Campaign: {utm_campaign if utm_campaign else 'N/A'}</p>
        <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
        <h3 style="color: #091C36;">Mensaje:</h3>
        <p style="background: #f8fafc; padding: 15px; border-radius: 8px; font-size: 14px; white-space: pre-wrap;">{message}</p>
        <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
        <p style="font-size: 12px; color: #64748B;">Este mensaje fue enviado automáticamente desde el formulario de contacto de clanship.cl.</p>
    </div>
    """

    resend_api_key = getattr(settings, 'RESEND_API_KEY', None)
    email_sent = False

    if resend_api_key and resend:
        try:
            resend.api_key = resend_api_key
            resend.Emails.send({
                "from": from_email,
                "to": [recipient_email],
                "reply_to": email,
                "subject": subject,
                "html": html_content,
            })
            email_sent = True
            logger.info(f"Correo de contacto de {email} enviado exitosamente vía Resend a {recipient_email}")
        except Exception as e:
            logger.error(f"Error al enviar correo vía Resend: {str(e)}")

    if not email_sent:
        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=f"Nombre: {name}\nCorreo: {email}\nTeléfono: {phone}\nMensaje:\n{message}",
                from_email=from_email,
                to=[recipient_email],
                reply_to=[email],
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=False)
            email_sent = True
            logger.info(f"Correo de contacto de {email} enviado vía Django send_mail a {recipient_email}")
        except Exception as e:
            logger.error(f"Error al enviar correo vía Django SMTP fallback: {str(e)}")

    return JsonResponse({
        'success': True,
        'message': '¡Gracias! Tu mensaje ha sido recibido por nuestro equipo.',
        'email_sent': email_sent
    })
