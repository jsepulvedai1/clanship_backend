from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Specialty, ProfessionalProfile

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Información de Clanship', {'fields': ('phone_number', 'user_type', 'avatar', 'is_available')}),
        ('Ubicación', {'fields': ('address', 'latitude', 'longitude')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Información de Clanship', {'fields': ('phone_number', 'user_type', 'avatar', 'is_available')}),
        ('Ubicación', {'fields': ('address', 'latitude', 'longitude')}),
    )
    list_display = ('username', 'email', 'phone_number', 'user_type', 'is_available', 'is_staff')
    list_filter = ('user_type', 'is_available', 'is_staff', 'is_superuser', 'is_active')

@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon')
    search_fields = ('name',)

@admin.register(ProfessionalProfile)
class ProfessionalProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'specialty', 'hourly_rate', 'rating', 'is_verified')
    list_filter = ('specialty', 'is_verified')
    search_fields = ('user__username', 'user__email')
