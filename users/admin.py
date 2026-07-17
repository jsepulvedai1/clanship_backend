from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin, TabularInline
from .models import User, Specialty, ProfessionalProfile, Tag, ProfessionalPhoto, ProfessionalDocument, SubscriptionPlan, UserAddress

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

class ProfessionalDocumentInline(TabularInline):
    model = ProfessionalDocument
    extra = 0

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

@admin.register(Tag)
class TagAdmin(ModelAdmin):
    list_display = ('name', 'specialty', 'color')
    list_filter = ('specialty',)
    search_fields = ('name', 'color', 'specialty__name')

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(ModelAdmin):
    list_display = ('name', 'price', 'duration_days')
    search_fields = ('name',)
    list_filter = ('price', 'duration_days')

@admin.register(ProfessionalPhoto)
class ProfessionalPhotoAdmin(ModelAdmin):
    list_display = ('id', 'profile', 'image', 'uploaded_at')
    list_filter = ('uploaded_at',)

@admin.register(ProfessionalProfile)
class ProfessionalProfileAdmin(ModelAdmin):
    inlines = [ProfessionalPhotoInline, ProfessionalDocumentInline]
    list_display = ('user', 'specialty', 'plan', 'hourly_rate', 'rating', 'service_radius', 'is_verified')
    list_filter = ('specialty', 'plan', 'is_verified')
    filter_horizontal = ('tags',)
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    actions = ['make_verified', 'make_unverified']

    @admin.action(description="Marcar perfiles seleccionados como VERIFICADOS")
    def make_verified(self, request, queryset):
        queryset.update(is_verified=True)
        self.message_user(request, "Los perfiles seleccionados han sido verificados con éxito.")

    @admin.action(description="Quitar verificación a los perfiles seleccionados")
    def make_unverified(self, request, queryset):
        queryset.update(is_verified=False)
        self.message_user(request, "Se ha retirado la verificación a los perfiles seleccionados.")


@admin.register(ProfessionalDocument)
class ProfessionalDocumentAdmin(ModelAdmin):
    list_display = ('name', 'profile', 'status', 'is_visible', 'uploaded_at')
    list_filter = ('status', 'is_visible', 'uploaded_at')
    search_fields = ('name', 'profile__user__username', 'profile__user__email')
    actions = ['approve_documents', 'reject_documents']

    @admin.action(description="Aprobar documentos seleccionados")
    def approve_documents(self, request, queryset):
        queryset.update(status='APPROVED')
        self.message_user(request, "Los documentos seleccionados han sido APROBADOS.")

    @admin.action(description="Rechazar documentos seleccionados")
    def reject_documents(self, request, queryset):
        queryset.update(status='REJECTED')
        self.message_user(request, "Los documentos seleccionados han sido RECHAZADOS.")



