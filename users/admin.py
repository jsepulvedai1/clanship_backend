from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin, TabularInline
from .models import User, Specialty, ProfessionalProfile, Tag, ProfessionalPhoto

class ProfessionalProfileInline(TabularInline):
    model = ProfessionalProfile
    extra = 0
    raw_id_fields = ('specialty',)

class ProfessionalPhotoInline(TabularInline):
    model = ProfessionalPhoto
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

@admin.register(Specialty)
class SpecialtyAdmin(ModelAdmin):
    list_display = ('name', 'icon')
    search_fields = ('name',)

@admin.register(Tag)
class TagAdmin(ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(ProfessionalPhoto)
class ProfessionalPhotoAdmin(ModelAdmin):
    list_display = ('id', 'profile', 'image', 'uploaded_at')
    list_filter = ('uploaded_at',)

@admin.register(ProfessionalProfile)
class ProfessionalProfileAdmin(ModelAdmin):
    inlines = [ProfessionalPhotoInline]
    list_display = ('user', 'specialty', 'hourly_rate', 'rating', 'service_radius', 'is_verified')
    list_filter = ('specialty', 'is_verified')
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


