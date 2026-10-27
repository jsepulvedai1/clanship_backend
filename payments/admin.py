from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from .models import PlanSubscriptionOrder


@admin.register(PlanSubscriptionOrder)
class PlanSubscriptionOrderAdmin(ModelAdmin):
    list_display = (
        'external_reference',
        'user_display',
        'plan_display',
        'amount_display',
        'status_badge',
        'mp_payment_id',
        'created_at',
        'paid_at',
    )
    list_filter = ('status', 'plan', 'created_at', 'currency')
    search_fields = (
        'external_reference',
        'preference_id',
        'mp_payment_id',
        'user__username',
        'user__email',
        'user__first_name',
        'user__last_name',
        'plan__name',
    )
    readonly_fields = (
        'id',
        'external_reference',
        'preference_id',
        'init_point',
        'sandbox_init_point',
        'mp_payment_id',
        'payment_method_id',
        'payment_type_id',
        'raw_webhook_data',
        'created_at',
        'updated_at',
        'paid_at',
    )

    @admin.display(description="Maestro")
    def user_display(self, obj):
        name = obj.user.get_full_name() or obj.user.username
        return f"{name} ({obj.user.email})"

    @admin.display(description="Plan")
    def plan_display(self, obj):
        return obj.plan.name

    @admin.display(description="Monto")
    def amount_display(self, obj):
        return f"${obj.amount:,.0f} {obj.currency}".replace(',', '.')

    @admin.display(description="Estado")
    def status_badge(self, obj):
        colors = {
            PlanSubscriptionOrder.Status.PENDING: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400 border border-amber-200 dark:border-amber-800/30",
            PlanSubscriptionOrder.Status.APPROVED: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/30",
            PlanSubscriptionOrder.Status.REJECTED: "bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-400 border border-rose-200 dark:border-rose-800/30",
            PlanSubscriptionOrder.Status.CANCELLED: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-400 border border-gray-300",
            PlanSubscriptionOrder.Status.REFUNDED: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400 border border-purple-200",
        }
        color_class = colors.get(obj.status, "bg-gray-100 text-gray-800")
        return format_html(
            '<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium {}">{}</span>',
            color_class,
            obj.get_status_display()
        )
