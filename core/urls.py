from django.contrib import admin
from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from graphene_django.views import GraphQLView
from django.contrib.auth import views as auth_views

import json

class CustomGraphQLView(GraphQLView):
    def dispatch(self, request, *args, **kwargs):
        try:
            body = request.body
        except Exception:
            body = b''
            
        response = super().dispatch(request, *args, **kwargs)
        if response.status_code == 400:
            print(f"=========================================")
            print(f"⚠️ GRAPHQL 400 BAD REQUEST DETECTED!")
            print(f"Request Body: {body}")
            print(f"Response Content: {response.content}")
            print(f"=========================================")
        return response

    @staticmethod
    def format_error(error):
        formatted = GraphQLView.format_error(error)
        original = getattr(error, 'original_error', None)
        
        user_message = getattr(original, 'user_message', None)
        code = getattr(original, 'code', None)

        # Si es un error de integridad de base de datos (ej. clave duplicada de teléfono o email)
        if not user_message and original:
            orig_name = type(original).__name__
            orig_str = str(original).lower()
            if 'integrity' in orig_name.lower() or 'unique' in orig_str:
                if 'phone' in orig_str:
                    user_message = 'El número de teléfono ya se encuentra registrado por otro usuario. Si ya tienes una cuenta, intenta iniciar sesión.'
                    code = 'PHONE_ALREADY_REGISTERED'
                elif 'email' in orig_str or 'username' in orig_str:
                    user_message = 'El correo electrónico ya se encuentra registrado por otro usuario. Si ya tienes una cuenta, intenta iniciar sesión.'
                    code = 'USER_ALREADY_EXISTS'

        # Si el error no es UserFacingError pero es Exception simple (ej: raise Exception('...'))
        if not user_message and original and isinstance(original, Exception):
            msg = str(original)
            technical_terms = ['syntaxerror', 'typeerror', 'attributeerror', 'operationalerror', 'traceback', 'internal server error']
            if not any(term in msg.lower() for term in technical_terms):
                user_message = msg

        if user_message:
            formatted['user_message'] = user_message
            formatted['message'] = user_message
            if 'extensions' not in formatted or not isinstance(formatted['extensions'], dict):
                formatted['extensions'] = {}
            formatted['extensions']['user_message'] = user_message

        if code:
            formatted['code'] = code
            if 'extensions' not in formatted or not isinstance(formatted['extensions'], dict):
                formatted['extensions'] = {}
            formatted['extensions']['code'] = code

        return formatted

from django.conf import settings
from django.conf.urls.static import static
from core.views import (
    contact_api_view, app_version_check_view, seasonal_config_api_view,
    secure_document_view, banners_api_view, admin_banners_api_view,
    admin_banner_toggle_api_view, admin_banners_reorder_api_view,
    admin_jobs_api_view
)
from payments.views import (
    mercadopago_webhook,
    payment_success_view,
    payment_failure_view,
    payment_pending_view
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path("graphql/", csrf_exempt(CustomGraphQLView.as_view(graphiql=True))),
    
    # Secure Document Viewer API
    path('api/v1/secure-document/<str:token>/', secure_document_view, name='secure_document'),
    
    # Contact Form API Endpoint
    path('api/v1/contact/', contact_api_view, name='contact_api'),
    
    # App Version Enforcement Check API Endpoint
    path('api/v1/app-version/', app_version_check_view, name='app_version_check'),
    
    # Seasonal Campaign & Theming API Endpoint
    path('api/v1/seasonal-config/', seasonal_config_api_view, name='seasonal_config_api'),
    path('api/v1/banners/', banners_api_view, name='banners_api'),

    # Admin Banners Management Endpoints (for clanship-admin)
    path('api/v1/admin/banners/', admin_banners_api_view, name='admin_banners_api'),
    path('api/v1/admin/banners/<int:banner_id>/', admin_banners_api_view, name='admin_banners_detail_api'),
    path('api/v1/admin/banners/<int:banner_id>/toggle/', admin_banner_toggle_api_view, name='admin_banner_toggle_api'),
    path('api/v1/admin/banners/reorder/', admin_banners_reorder_api_view, name='admin_banners_reorder_api'),

    # Admin Jobs Management Endpoints (for clanship-admin)
    path('api/v1/admin/jobs/', admin_jobs_api_view, name='admin_jobs_api'),
    path('api/v1/admin/jobs/<int:job_id>/', admin_jobs_api_view, name='admin_jobs_detail_api'),
    
    # Mercado Pago Webhooks & Callbacks
    path('api/payments/mercadopago/webhook/', mercadopago_webhook, name='mercadopago_webhook'),
    path('api/payments/mercadopago/success/', payment_success_view, name='mercadopago_success'),
    path('api/payments/mercadopago/failure/', payment_failure_view, name='mercadopago_failure'),
    path('api/payments/mercadopago/pending/', payment_pending_view, name='mercadopago_pending'),
    
    # Restablecimiento de contraseña
    path(
        'auth/reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html',
            success_url='/auth/reset/done/'
        ),
        name='password_reset_confirm'
    ),
    path(
        'auth/reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html'
        ),
        name='password_reset_complete'
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler400 = 'core.views.custom_400_view'
handler403 = 'core.views.custom_403_view'
handler404 = 'core.views.custom_404_view'
handler500 = 'core.views.custom_500_view'

