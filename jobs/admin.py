from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from .models import Job

@admin.register(Job)
class JobAdmin(ModelAdmin):
    list_display = ('id', 'customer', 'professional', 'scheduled_date', 'status_badge', 'agreed_price', 'created_at')
    list_filter = ('status', 'scheduled_date')
    search_fields = (
        'customer__username', 'customer__first_name', 'customer__last_name',
        'professional__username', 'professional__first_name', 'professional__last_name',
        'description'
    )
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description="Estado")
    def status_badge(self, obj):
        colors = {
            Job.Status.REQUESTED: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400 border border-amber-200 dark:border-amber-800/30",
            Job.Status.AGREED: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400 border border-blue-200 dark:border-blue-800/30",
            Job.Status.IN_VISIT: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400 border border-purple-200 dark:border-purple-800/30",
            Job.Status.FINISHED: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/30",
            Job.Status.CANCELLED: "bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-400 border border-rose-200 dark:border-rose-800/30",
        }
        color_class = colors.get(obj.status, "bg-gray-100 text-gray-800")
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {}">{}</span>',
            color_class,
            obj.get_status_display()
        )

