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

from django.utils import timezone
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from users.models import User, ProfessionalProfile, AppVersionConfig, SeasonalCampaign
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


@csrf_exempt
def app_version_check_view(request):
    """
    Endpoint para verificar la versión mínima requerida de las aplicaciones móviles.
    Permite realizar bloqueo de versiones antiguas (Force Update).
    Lee la configuración desde Django Admin (AppVersionConfig) con fallback a settings.py.
    """
    app_type = request.GET.get('app_type', 'CLIENT').upper()
    platform = request.GET.get('platform', 'android').lower()
    current_version = request.GET.get('version', '1.0.0').strip()

    cache_key = f"app_ver_{app_type}_{platform}_{current_version}"
    cached_payload = cache.get(cache_key)
    if cached_payload is not None:
        return JsonResponse(cached_payload)

    # Intentar obtener la configuración desde la BD (Django Admin)
    db_config = AppVersionConfig.objects.filter(app_type=app_type, is_active=True).first()

    if db_config:
        min_v = db_config.min_version
        latest_v = db_config.latest_version
        store_url = db_config.store_url_ios if platform == 'ios' else db_config.store_url_android
        store_url = store_url or ''
        title_custom = db_config.title
        message_custom = db_config.message
    else:
        # Fallback a settings si no hay registro creado en BD aún
        if app_type == 'TRADESMAN':
            min_v = getattr(settings, 'MIN_TRADESMAN_VERSION', '1.0.0')
            latest_v = getattr(settings, 'LATEST_TRADESMAN_VERSION', '1.0.0')
            store_url = getattr(settings, 'TRADESMAN_STORE_URL_IOS' if platform == 'ios' else 'TRADESMAN_STORE_URL_ANDROID', '')
        else:
            min_v = getattr(settings, 'MIN_CLIENT_VERSION', '1.0.0')
            latest_v = getattr(settings, 'LATEST_CLIENT_VERSION', '1.0.0')
            store_url = getattr(settings, 'CLIENT_STORE_URL_IOS' if platform == 'ios' else 'CLIENT_STORE_URL_ANDROID', '')
        title_custom = None
        message_custom = None

    def parse_version(v_str):
        try:
            return [int(x) for x in v_str.split('.')]
        except Exception:
            return [1, 0, 0]

    cur_parts = parse_version(current_version)
    min_parts = parse_version(min_v)
    latest_parts = parse_version(latest_v)

    update_required = cur_parts < min_parts
    update_recommended = cur_parts < latest_parts and not update_required

    default_title = 'Actualización Requerida' if update_required else 'Actualización Disponible'
    default_message = 'Para continuar usando Clanship de manera segura, por favor actualiza la aplicación a la última versión disponible.' if update_required else 'Hay una nueva versión disponible con mejoras y correcciones.'

    response_data = {
        'success': True,
        'app_type': app_type,
        'current_version': current_version,
        'min_version': min_v,
        'latest_version': latest_v,
        'update_required': update_required,
        'update_recommended': update_recommended,
        'store_url': store_url,
        'title': title_custom or default_title,
        'message': message_custom or default_message
    }
    cache.set(cache_key, response_data, 300)
    return JsonResponse(response_data)


@csrf_exempt
def seasonal_config_api_view(request):
    """
    Endpoint para entregar la configuración visual y temática de festividades (Remote Theming).
    Permite activar paletas de colores, insignias sobre el logo, banners y animaciones
    de forma remota según la fecha actual y la prioridad de la campaña configurada en Django Admin.
    """
    app_type = request.GET.get('app_type', 'CLIENT').upper()

    cache_key = f"seasonal_cfg_{app_type}"
    cached_payload = cache.get(cache_key)
    if cached_payload is not None:
        return JsonResponse(cached_payload)

    now = timezone.now()

    campaign = SeasonalCampaign.objects.filter(
        is_active=True,
        app_type__in=[app_type, 'ALL'],
        start_date__lte=now,
        end_date__gte=now,
    ).order_by('-priority', '-id').first()

    if not campaign:
        empty_payload = {
            'success': True,
            'has_active_campaign': False,
            'campaign': None
        }
        cache.set(cache_key, empty_payload, 300)
        return JsonResponse(empty_payload)

    # Serializar tags destacados
    featured_tags_data = [
        {'id': t.id, 'name': t.name}
        for t in campaign.featured_tags.all()
    ]

    # Construir URLs absolutas de assets (asegurando HTTPS en producción)
    def to_https(url_str):
        if not url_str:
            return None
        if not settings.DEBUG and url_str.startswith('http://'):
            return url_str.replace('http://', 'https://', 1)
        return url_str

    logo_badge_url = to_https(request.build_absolute_uri(campaign.logo_badge_icon.url)) if campaign.logo_badge_icon else None
    nav_center_icon_url = to_https(request.build_absolute_uri(campaign.nav_center_icon.url)) if campaign.nav_center_icon else None
    custom_garland_url = to_https(request.build_absolute_uri(campaign.custom_garland_image.url)) if campaign.custom_garland_image else None
    banner_image_url = to_https(request.build_absolute_uri(campaign.banner_image.url)) if campaign.banner_image else None
    stat_cards_bg_image_url = to_https(request.build_absolute_uri(campaign.stat_cards_bg_image.url)) if campaign.stat_cards_bg_image else None
    stat_card_active_bg_image_url = to_https(request.build_absolute_uri(campaign.stat_card_active_bg_image.url)) if campaign.stat_card_active_bg_image else None
    stat_card_completed_bg_image_url = to_https(request.build_absolute_uri(campaign.stat_card_completed_bg_image.url)) if campaign.stat_card_completed_bg_image else None
    stat_card_rejected_bg_image_url = to_https(request.build_absolute_uri(campaign.stat_card_rejected_bg_image.url)) if campaign.stat_card_rejected_bg_image else None
    stat_card_scheduled_bg_image_url = to_https(request.build_absolute_uri(campaign.stat_card_scheduled_bg_image.url)) if campaign.stat_card_scheduled_bg_image else None

    response_data = {
        'success': True,
        'has_active_campaign': True,
        'campaign': {
            'id': campaign.id,
            'name': campaign.name,
            'season_type': campaign.season_type,
            'colors': {
                'primary': campaign.primary_color,
                'secondary': campaign.secondary_color,
                'accent': campaign.accent_color,
                'header_gradient_start': campaign.header_gradient_start,
                'header_gradient_end': campaign.header_gradient_end,
                'search_bar_border': campaign.search_bar_border_color,
                'nav_center': campaign.nav_center_color,
                'stat_cards_bg': campaign.stat_cards_bg_color,
                'stat_cards_number': campaign.stat_cards_number_color,
                'stat_cards_text': campaign.stat_cards_text_color,
                'stat_cards_icon': campaign.stat_cards_icon_color,
                'stat_card_active_bg': campaign.stat_card_active_bg_color,
                'stat_card_active_number': campaign.stat_card_active_number_color,
                'stat_card_active_text': campaign.stat_card_active_text_color,
                'stat_card_active_icon': campaign.stat_card_active_icon_color,
                'stat_card_completed_bg': campaign.stat_card_completed_bg_color,
                'stat_card_completed_number': campaign.stat_card_completed_number_color,
                'stat_card_completed_text': campaign.stat_card_completed_text_color,
                'stat_card_completed_icon': campaign.stat_card_completed_icon_color,
                'stat_card_rejected_bg': campaign.stat_card_rejected_bg_color,
                'stat_card_rejected_number': campaign.stat_card_rejected_number_color,
                'stat_card_rejected_text': campaign.stat_card_rejected_text_color,
                'stat_card_rejected_icon': campaign.stat_card_rejected_icon_color,
                'stat_card_scheduled_bg': campaign.stat_card_scheduled_bg_color,
                'stat_card_scheduled_number': campaign.stat_card_scheduled_number_color,
                'stat_card_scheduled_text': campaign.stat_card_scheduled_text_color,
                'stat_card_scheduled_icon': campaign.stat_card_scheduled_icon_color,
            },
            'visuals': {
                'logo_badge_url': logo_badge_url,
                'nav_center_icon_url': nav_center_icon_url,
                'show_top_garland': campaign.show_top_garland,
                'garland_position': campaign.garland_position,
                'show_garland_top': campaign.show_top_garland and campaign.garland_position in ['BOTH', 'TOP'],
                'show_garland_bottom': campaign.show_top_garland and campaign.garland_position in ['BOTH', 'BOTTOM'],
                'custom_garland_url': custom_garland_url,
                'banner_image_url': banner_image_url,
                'stat_cards_bg_image_url': stat_cards_bg_image_url,
                'stat_card_active_bg_image_url': stat_card_active_bg_image_url,
                'stat_card_completed_bg_image_url': stat_card_completed_bg_image_url,
                'stat_card_rejected_bg_image_url': stat_card_rejected_bg_image_url,
                'stat_card_scheduled_bg_image_url': stat_card_scheduled_bg_image_url,
                'stat_cards_image_opacity': campaign.stat_cards_image_opacity,
                'stat_card_active_image_opacity': campaign.stat_card_active_image_opacity,
                'stat_card_completed_image_opacity': campaign.stat_card_completed_image_opacity,
                'stat_card_rejected_image_opacity': campaign.stat_card_rejected_image_opacity,
                'stat_card_scheduled_image_opacity': campaign.stat_card_scheduled_image_opacity,
                'particle_effect': campaign.particle_effect,
            },
            'copy': {
                'greeting_prefix': campaign.greeting_prefix,
                'promo_banner_title': campaign.promo_banner_title,
                'promo_banner_subtitle': campaign.promo_banner_subtitle,
                'promo_banner_cta_text': campaign.promo_banner_cta_text,
                'promo_banner_action_type': campaign.promo_banner_action_type,
                'promo_banner_action_value': campaign.promo_banner_action_value,
            },
            'featured_tags': featured_tags_data,
        }
    }
    cache.set(cache_key, response_data, 300)
    return JsonResponse(response_data)


@receiver([post_save, post_delete], sender=AppVersionConfig)
def clear_app_version_cache(sender, **kwargs):
    try:
        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern("*app_ver_*")
    except Exception as e:
        logger.warning(f"Error invalidating app version cache: {e}")


@receiver([post_save, post_delete], sender=SeasonalCampaign)
def clear_seasonal_cache(sender, **kwargs):
    try:
        cache.delete("seasonal_cfg_CLIENT")
        cache.delete("seasonal_cfg_TRADESMAN")
        cache.delete("seasonal_cfg_ALL")
        if hasattr(cache, 'delete_pattern'):
            cache.delete_pattern("*seasonal_cfg_*")
    except Exception as e:
        logger.warning(f"Error invalidating seasonal config cache: {e}")

