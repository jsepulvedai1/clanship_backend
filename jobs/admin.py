from django.contrib import admin
from .models import Job

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'professional', 'scheduled_date', 'status', 'agreed_price')
    list_filter = ('status', 'scheduled_date')
    search_fields = ('customer__username', 'professional__username', 'description')
    readonly_fields = ('created_at', 'updated_at')
