from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html, mark_safe
from django.urls import path, reverse
from django.shortcuts import get_object_or_404, redirect
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display, action
from .models import User, Specialty, ProfessionalProfile, Tag, SubTag, ProfessionalPhoto, ProfessionalDocument, SubscriptionPlan, UserAddress, UserDevice, SystemSetting, AppVersionConfig

@admin.register(AppVersionConfig)
class AppVersionConfigAdmin(ModelAdmin):
    list_display = ('app_type', 'min_version', 'latest_version', 'is_active', 'updated_at')
    list_filter = ('app_type', 'is_active')
    search_fields = ('app_type', 'min_version', 'latest_version')
    fieldsets = (
        ('Información Principal', {
            'fields': ('app_type', 'is_active', 'min_version', 'latest_version')
        }),
        ('Enlaces de Tiendas', {
            'fields': ('store_url_android', 'store_url_ios')
        }),
        ('Mensaje de Bloqueo', {
            'fields': ('title', 'message')
        }),
    )

@admin.register(SystemSetting)
class SystemSettingAdmin(ModelAdmin):
    list_display = ('max_specialties_per_tradesman',)

@admin.register(UserDevice)
class UserDeviceAdmin(ModelAdmin):
    list_display = ('user', 'fcm_token_truncated', 'created_at', 'updated_at')
    search_fields = ('user__username', 'fcm_token')
    list_filter = ('created_at', 'updated_at')

    def fcm_token_truncated(self, obj):
        return f"{obj.fcm_token[:30]}..." if obj.fcm_token else ""
    fcm_token_truncated.short_description = 'FCM Token'

@admin.register(UserAddress)
class UserAddressAdmin(ModelAdmin):
    list_display = ('user', 'alias', 'address', 'latitude', 'longitude')
    search_fields = ('user__username', 'alias', 'address')
    list_filter = ('user',)

class ProfessionalProfileInline(TabularInline):
    model = ProfessionalProfile
    extra = 0
    raw_id_fields = ('specialty', )

class ProfessionalPhotoInline(TabularInline):
    model = ProfessionalPhoto
    extra = 0
    readonly_fields = ('photo_preview',)

    def photo_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 80px; border-radius: 8px; object-fit: cover;" />', obj.image.url)
        return "Sin imagen"
    photo_preview.short_description = "Vista Previa"

class ProfessionalDocumentInline(TabularInline):
    model = ProfessionalDocument
    extra = 0
    readonly_fields = ('document_preview',)

    def document_preview(self, obj):
        if obj.file:
            url = obj.file.url
            if url.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                return format_html('<a href="{}" target="_blank"><img src="{}" style="max-height: 80px; border-radius: 8px; object-fit: cover;" /></a>', url, url)
            return format_html('<a href="{}" target="_blank" class="button">📄 Ver Documento</a>', url)
        return "Sin archivo"
    document_preview.short_description = "Vista Previa"

@admin.register(User)
class CustomUserAdmin(ModelAdmin, BaseUserAdmin):
    inlines = [ProfessionalProfileInline]
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Información de Clanship', {'fields': ('phone_number', 'user_type', 'avatar', 'is_available', 'favorite_professionals')}),
        ('Ubicación', {'fields': ('address', 'latitude', 'longitude')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Información de Clanship', {'fields': ('phone_number', 'user_type', 'avatar', 'is_available')}),
        ('Ubicación', {'fields': ('address', 'latitude', 'longitude')}),
    )
    list_display = ('username', 'email', 'phone_number', 'user_type', 'is_available', 'is_staff' , 'avatar')
    list_filter = ('user_type', 'is_available', 'is_staff', 'is_superuser', 'is_active')
    filter_horizontal = ('favorite_professionals',)

class TagInline(TabularInline):
    model = Tag
    extra = 1
    fields = ('name', 'color', 'synonyms')

@admin.register(Specialty)
class SpecialtyAdmin(ModelAdmin):
    list_display = ('name', 'icon', 'color')
    search_fields = ('name', 'color')
    inlines = [TagInline]

class SubTagInline(TabularInline):
    model = SubTag
    extra = 1
    fields = ('name', 'color')

@admin.register(Tag)
class TagAdmin(ModelAdmin):
    list_display = ('name', 'specialty', 'color', 'icon')
    list_filter = ('specialty',)
    search_fields = ('name', 'color', 'specialty__name')
    inlines = [SubTagInline]

@admin.register(SubTag)
class SubTagAdmin(ModelAdmin):
    list_display = ('name', 'tag', 'color')
    list_filter = ('tag__specialty', 'tag')
    search_fields = ('name', 'color', 'tag__name')

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(ModelAdmin):
    list_display = ('display_order', 'name', 'price', 'is_coming_soon', 'duration_days', 'monthly_requests', 'urgent_requests', 'service_categories', 'search_position', 'featured_badge', 'support_level')
    list_display_links = ('name',)
    list_editable = ('display_order', 'is_coming_soon')
    search_fields = ('name',)
    list_filter = ('is_coming_soon', 'price', 'duration_days', 'search_position', 'support_level')
    ordering = ('display_order', 'id')

@admin.register(ProfessionalPhoto)
class ProfessionalPhotoAdmin(ModelAdmin):
    list_display = ('id', 'profile', 'image', 'uploaded_at')
    list_filter = ('uploaded_at',)

@admin.register(ProfessionalProfile)
class ProfessionalProfileAdmin(ModelAdmin):
    inlines = [ProfessionalPhotoInline, ProfessionalDocumentInline]
    list_display = (
        'avatar_preview', 
        'user_name_and_contact', 
        'specialty', 
        'plan', 
        'documents_summary', 
        'photos_count', 
        'verification_badge', 
        'quick_action'
    )
    list_filter = ('is_verified', 'specialty', 'plan')
    filter_horizontal = ('tags', 'subtags', 'specialties')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name', 'user__phone_number')
    actions = ['make_verified', 'make_unverified']
    readonly_fields = ('verification_banner', 'documents_and_photos_gallery')

    fieldsets = (
        ('Información del Profesional', {
            'fields': ('user', 'specialty', 'specialties', 'plan', 'bio', 'hourly_rate', 'rating', 'service_radius')
        }),
        ('Estado de Habilitación y Verificación', {
            'fields': ('is_verified', 'verification_banner')
        }),
        ('Galería de Fotos y Documentos', {
            'fields': ('documents_and_photos_gallery',)
        }),
        ('Categorías y Oficios', {
            'fields': ('tags', 'subtags')
        }),
        ('Ubicación y Contacto', {
            'fields': ('address', 'latitude', 'longitude', 'facebook_url', 'instagram_url', 'tiktok_url')
        }),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:profile_id>/toggle-verify/', 
                self.admin_site.admin_view(self.toggle_verification_view), 
                name='users_professionalprofile_toggle_verify'
            ),
        ]
        return custom_urls + urls

    def toggle_verification_view(self, request, profile_id):
        profile = get_object_or_404(ProfessionalProfile, pk=profile_id)
        profile.is_verified = not profile.is_verified
        profile.save()
        status_str = "HABILITADO Y VERIFICADO" if profile.is_verified else "DESHABILITADO"
        user_name = profile.user.get_full_name() or profile.user.username
        self.message_user(
            request, 
            f"El perfil de {user_name} ha sido marcado como {status_str}.", 
            level=messages.SUCCESS
        )
        return redirect(request.META.get('HTTP_REFERER', reverse('admin:users_professionalprofile_changelist')))

    @display(description="Foto")
    def avatar_preview(self, obj):
        if obj.user and obj.user.avatar:
            return format_html('<img src="{}" class="profile-avatar-img" />', obj.user.avatar.url)
        initial = (obj.user.first_name[:1] if obj.user and obj.user.first_name else 'P').upper()
        return format_html('<div class="profile-avatar-placeholder">{}</div>', initial)

    @display(description="Profesional / Contacto")
    def user_name_and_contact(self, obj):
        if not obj.user:
            return "Sin usuario"
        full_name = obj.user.get_full_name() or obj.user.username
        email = obj.user.email or "Sin correo"
        phone = obj.user.phone_number or "Sin teléfono"
        return format_html(
            '<div><strong>{}</strong><br/><span style="color: #64748b; font-size: 0.8rem;">✉ {} | 📞 {}</span></div>',
            full_name, email, phone
        )

    @display(description="Documentos")
    def documents_summary(self, obj):
        docs = obj.documents.all()
        count = docs.count()
        if count == 0:
            return format_html('<span style="color: #94a3b8; font-size: 0.8rem;">Sin documentos</span>')
        approved = docs.filter(status='APPROVED').count()
        pending = docs.filter(status='PENDING').count()
        return format_html(
            '<div style="font-size: 0.8rem;"><strong>{} doc(s)</strong><br/><span style="color: #059669;">✓ {} aprobados</span> | <span style="color: #d97706;">⏳ {} pendientes</span></div>',
            count, approved, pending
        )

    @display(description="Fotos Portafolio")
    def photos_count(self, obj):
        count = obj.photos.count()
        return format_html('<span>📷 {} foto(s)</span>', count)

    @display(description="Estado")
    def verification_badge(self, obj):
        if obj.is_verified:
            return format_html('<span class="badge-status-verified">✓ Habilitado</span>')
        return format_html('<span class="badge-status-pending">⏳ Pendiente</span>')

    @display(description="Acción Rápida")
    def quick_action(self, obj):
        url = reverse('admin:users_professionalprofile_toggle_verify', args=[obj.pk])
        if obj.is_verified:
            return format_html('<a href="{}" class="btn-verify-action unverify">Deshabilitar</a>', url)
        return format_html('<a href="{}" class="btn-verify-action verify">✓ Habilitar</a>', url)

    def verification_banner(self, obj):
        if not obj:
            return ""
        if obj.is_verified:
            return format_html(
                '<div style="background-color: #d1fae5; border: 1px solid #a7f3d0; color: #065f46; padding: 12px 16px; border-radius: 8px; font-weight: 600;">'
                '✓ Este perfil profesional está VERIFICADO y HABILITADO para recibir trabajos.'
                '</div>'
            )
        return format_html(
            '<div style="background-color: #fef3c7; border: 1px solid #fde68a; color: #92400e; padding: 12px 16px; border-radius: 8px; font-weight: 600;">'
            '⏳ Este perfil está PENDIENTE DE REVISIÓN y deshabilitado para recibir trabajos en la app.'
            '</div>'
        )
    verification_banner.short_description = "Estado de Verificación Actual"

    def documents_and_photos_gallery(self, obj):
        if not obj or not obj.pk:
            return "Guarda el perfil primero para adjuntar documentos o fotos."

        html = ['<div style="background: #ffffff; padding: 16px; border: 1px solid #e2e8f0; border-radius: 12px;">']

        # Avatar foto
        html.append('<h4 style="font-weight: 700; color: #0d2b45; margin-bottom: 10px;">Foto de Perfil del Usuario:</h4>')
        if obj.user and obj.user.avatar:
            html.append(f'<div style="margin-bottom: 20px;"><a href="{obj.user.avatar.url}" target="_blank"><img src="{obj.user.avatar.url}" style="max-height: 160px; border-radius: 12px; border: 2px solid #e2e8f0; object-fit: cover;" /></a></div>')
        else:
            html.append('<p style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 20px;">No ha subido foto de perfil.</p>')

        # Documentos
        docs = obj.documents.all()
        html.append('<h4 style="font-weight: 700; color: #0d2b45; margin-bottom: 10px;">Documentos y Certificados Registrados:</h4>')
        if docs.exists():
            html.append('<div class="doc-gallery-grid">')
            for doc in docs:
                file_url = doc.file.url if doc.file else '#'
                is_img = file_url.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
                status_color = '#10b981' if doc.status == 'APPROVED' else ('#ef4444' if doc.status == 'REJECTED' else '#f59e0b')
                
                html.append('<div class="doc-card-item">')
                if is_img:
                    html.append(f'<a href="{file_url}" target="_blank"><img src="{file_url}" /></a>')
                else:
                    html.append(f'<div style="height: 100px; display: flex; align-items: center; justify-content: center; background: #f1f5f9; border-radius: 8px; font-size: 32px;">📄</div>')
                
                html.append(f'<div style="font-weight: 600; font-size: 0.85rem; color: #1e293b; margin-top: 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">{doc.name}</div>')
                html.append(f'<div style="font-size: 0.75rem; color: {status_color}; font-weight: 700; margin-top: 4px;">{doc.get_status_display()}</div>')
                html.append(f'<a href="{file_url}" target="_blank" style="font-size: 0.75rem; color: #0284c7; text-decoration: underline; display: block; margin-top: 4px;">Ver Archivo</a>')
                html.append('</div>')
            html.append('</div>')
        else:
            html.append('<p style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 20px;">Sin documentos adjuntos.</p>')

        # Fotos de Portafolio
        photos = obj.photos.all()
        html.append('<h4 style="font-weight: 700; color: #0d2b45; margin-top: 16px; margin-bottom: 10px;">Fotos del Portafolio de Trabajos:</h4>')
        if photos.exists():
            html.append('<div class="doc-gallery-grid">')
            for p in photos:
                if p.image:
                    html.append(f'<div class="doc-card-item"><a href="{p.image.url}" target="_blank"><img src="{p.image.url}" /></a><span style="font-size: 0.75rem; color: #64748b;">Trabajo Portafolio</span></div>')
            html.append('</div>')
        else:
            html.append('<p style="color: #94a3b8; font-size: 0.9rem;">Sin fotos de portafolio.</p>')

        html.append('</div>')
        return mark_safe(''.join(html))
    documents_and_photos_gallery.short_description = "Galería Completa de Fotos y Documentación"

    @admin.action(description="Marcar perfiles seleccionados como HABILITADOS / VERIFICADOS")
    def make_verified(self, request, queryset):
        for profile in queryset:
            profile.is_verified = True
            profile.save()
        self.message_user(request, "Los perfiles seleccionados han sido verificados y habilitados con éxito.", level=messages.SUCCESS)

    @admin.action(description="Quitar habilitación / verificación a los perfiles seleccionados")
    def make_unverified(self, request, queryset):
        for profile in queryset:
            profile.is_verified = False
            profile.save()
        self.message_user(request, "Se ha deshabilitado la verificación a los perfiles seleccionados.", level=messages.SUCCESS)

@admin.register(ProfessionalDocument)
class ProfessionalDocumentAdmin(ModelAdmin):
    list_display = ('name', 'profile', 'status', 'is_visible', 'uploaded_at')
    list_filter = ('status', 'is_visible', 'uploaded_at')
    search_fields = ('name', 'profile__user__username', 'profile__user__email')
    actions = ['approve_documents', 'reject_documents']

    @admin.action(description="Aprobar documentos seleccionados")
    def approve_documents(self, request, queryset):
        for doc in queryset:
            doc.status = 'APPROVED'
            doc.save()
            if doc.profile:
                doc.profile.is_verified = True
                doc.profile.save()
        self.message_user(request, "Los documentos seleccionados han sido APROBADOS y el perfil ha sido habilitado.", level=messages.SUCCESS)

    @admin.action(description="Rechazar documentos seleccionados")
    def reject_documents(self, request, queryset):
        for doc in queryset:
            doc.status = 'REJECTED'
            doc.save()
        self.message_user(request, "Los documentos seleccionados han sido RECHAZADOS.", level=messages.SUCCESS)
