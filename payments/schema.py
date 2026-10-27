import graphene
from graphene_django import DjangoObjectType
from django.utils import timezone
from django.contrib.auth import get_user_model
from users.models import SubscriptionPlan, ProfessionalProfile
from users.schema import ProfessionalProfileType
from .models import PlanSubscriptionOrder
from .services import create_plan_subscription_preference, process_mercadopago_payment

User = get_user_model()


class PlanSubscriptionOrderType(DjangoObjectType):
    class Meta:
        model = PlanSubscriptionOrder
        fields = (
            'id',
            'amount',
            'currency',
            'status',
            'external_reference',
            'preference_id',
            'init_point',
            'sandbox_init_point',
            'created_at',
            'updated_at',
            'paid_at',
        )

    checkout_url = graphene.String()

    def resolve_checkout_url(self, info):
        from django.conf import settings
        if settings.DEBUG and self.sandbox_init_point:
            return self.sandbox_init_point
        return self.init_point or self.sandbox_init_point


class CreatePlanSubscriptionPayment(graphene.Mutation):
    """
    Inicia la suscripción a un plan.
    - Si el plan es gratuito ($0), lo activa directamente.
    - Si es de pago, crea la preferencia de Mercado Pago y retorna la URL de pago.
    """
    class Arguments:
        plan_id = graphene.ID(required=True)
        return_url = graphene.String(required=False)

    success = graphene.Boolean()
    requires_payment = graphene.Boolean()
    checkout_url = graphene.String()
    preference_id = graphene.String()
    message = graphene.String()
    order = graphene.Field(PlanSubscriptionOrderType)
    profile = graphene.Field(ProfessionalProfileType)

    def mutate(self, info, plan_id, return_url=None):
        user = info.context.user
        if not user.is_authenticated:
            raise Exception('No autenticado')
        if getattr(user, 'user_type', None) != User.UserType.PROFESSIONAL:
            raise Exception('El usuario debe ser un profesional / maestro')

        try:
            profile = user.professional_profile
        except ProfessionalProfile.DoesNotExist:
            raise Exception('Perfil profesional no encontrado')

        try:
            plan = SubscriptionPlan.objects.get(pk=plan_id)
        except SubscriptionPlan.DoesNotExist:
            raise Exception('El plan especificado no existe')

        if plan.is_coming_soon:
            raise Exception('Este plan estará disponible próximamente.')

        if plan.service_categories is not None:
            current_tags = profile.tags.count()
            if current_tags > plan.service_categories:
                raise Exception(
                    f'El plan {plan.name} solo permite {plan.service_categories} oficios, pero tienes {current_tags} seleccionados. Por favor, desmarca algunos antes de cambiar de plan.'
                )

        # Caso 1: Plan Gratuito ($0) -> Activación inmediata
        if plan.price <= 0:
            profile.plan = plan
            profile.plan_start_date = timezone.now()
            duration = plan.duration_days or 30
            profile.plan_expires_at = timezone.now() + timezone.timedelta(days=duration)
            profile.save(update_fields=['plan', 'plan_start_date', 'plan_expires_at'])

            return CreatePlanSubscriptionPayment(
                success=True,
                requires_payment=False,
                checkout_url=None,
                preference_id=None,
                message=f'Plan {plan.name} activado con éxito.',
                order=None,
                profile=profile
            )

        # Caso 2: Plan de Pago -> Generar preferencia Mercado Pago
        try:
            pref_result = create_plan_subscription_preference(
                user=user,
                plan=plan,
                base_return_url=return_url
            )
            return CreatePlanSubscriptionPayment(
                success=True,
                requires_payment=True,
                checkout_url=pref_result["checkout_url"],
                preference_id=pref_result["preference_id"],
                message='Preferencia de pago creada. Procede al checkout.',
                order=pref_result["order"],
                profile=profile
            )
        except Exception as e:
            raise Exception(f'Error al generar pago en Mercado Pago: {str(e)}')


class CheckPlanPaymentStatus(graphene.Mutation):
    """
    Verifica el estado de una orden de pago tras el retorno del maestro a la app.
    """
    class Arguments:
        order_id = graphene.ID(required=False)
        external_reference = graphene.String(required=False)

    success = graphene.Boolean()
    is_paid = graphene.Boolean()
    status = graphene.String()
    order = graphene.Field(PlanSubscriptionOrderType)
    profile = graphene.Field(ProfessionalProfileType)

    def mutate(self, info, order_id=None, external_reference=None):
        user = info.context.user
        if not user.is_authenticated:
            raise Exception('No autenticado')

        filters = {'user': user}
        if order_id:
            filters['id'] = order_id
        elif external_reference:
            filters['external_reference'] = external_reference
        else:
            raise Exception('Debes proporcionar order_id o external_reference')

        try:
            order = PlanSubscriptionOrder.objects.get(**filters)
        except PlanSubscriptionOrder.DoesNotExist:
            raise Exception('Orden de pago no encontrada')

        profile = getattr(user, 'professional_profile', None)
        is_paid = (order.status == PlanSubscriptionOrder.Status.APPROVED)

        return CheckPlanPaymentStatus(
            success=True,
            is_paid=is_paid,
            status=order.status,
            order=order,
            profile=profile
        )


class Query(graphene.ObjectType):
    my_subscription_orders = graphene.List(PlanSubscriptionOrderType)

    def resolve_my_subscription_orders(self, info):
        user = info.context.user
        if not user.is_authenticated:
            return []
        return PlanSubscriptionOrder.objects.filter(user=user)


class Mutation(graphene.ObjectType):
    create_plan_subscription_payment = CreatePlanSubscriptionPayment.Field()
    check_plan_payment_status = CheckPlanPaymentStatus.Field()
