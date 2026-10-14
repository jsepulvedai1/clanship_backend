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

from django.conf import settings
from django.conf.urls.static import static
from core.views import (
    contact_api_view, app_version_check_view, seasonal_config_api_view,
    secure_document_view, banners_api_view, admin_banners_api_view,
    admin_banner_toggle_api_view, admin_banners_reorder_api_view
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
