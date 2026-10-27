from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from users.models import SubscriptionPlan, ProfessionalProfile, Specialty
from payments.models import PlanSubscriptionOrder
from payments.services import create_plan_subscription_preference, process_mercadopago_payment
from unittest.mock import patch, MagicMock

User = get_user_model()


class PaymentsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="maestro_test",
            email="maestro@test.cl",
            password="password123",
            user_type=User.UserType.PROFESSIONAL,
            first_name="Juan",
            last_name="Perez"
        )
        self.specialty = Specialty.objects.create(name="Gasfitería")
        self.profile = ProfessionalProfile.objects.create(
            user=self.user,
            specialty=self.specialty
        )

        self.free_plan = SubscriptionPlan.objects.create(
            name="Plan Básico Test",
            price=0.00,
            duration_days=30
        )
        self.paid_plan = SubscriptionPlan.objects.create(
            name="Plan Profesional Test",
            price=9990.00,
            duration_days=30
        )

    @patch('payments.services.get_mercadopago_sdk')
    def test_create_preference_paid_plan(self, mock_sdk_fn):
        mock_sdk = MagicMock()
        mock_sdk_fn.return_value = mock_sdk
        mock_sdk.preference().create.return_value = {
            "status": 201,
            "response": {
                "id": "pref_test_123456",
                "init_point": "https://www.mercadopago.cl/checkout/v1/redirect?pref_id=pref_test_123456",
                "sandbox_init_point": "https://sandbox.mercadopago.cl/checkout/v1/redirect?pref_id=pref_test_123456"
            }
        }

        result = create_plan_subscription_preference(self.user, self.paid_plan)

        self.assertIsNotNone(result)
        self.assertEqual(result["preference_id"], "pref_test_123456")
        order = result["order"]
        self.assertEqual(order.status, PlanSubscriptionOrder.Status.PENDING)
        self.assertEqual(order.amount, 9990.00)
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.plan, self.paid_plan)

    @patch('payments.services.get_mercadopago_sdk')
    def test_process_webhook_approval(self, mock_sdk_fn):
        order = PlanSubscriptionOrder.objects.create(
            user=self.user,
            plan=self.paid_plan,
            amount=9990.00,
            currency="CLP",
            status=PlanSubscriptionOrder.Status.PENDING,
            external_reference="TEST-ORDER-REF-1"
        )

        mock_sdk = MagicMock()
        mock_sdk_fn.return_value = mock_sdk
        mock_sdk.payment().get.return_value = {
            "status": 200,
            "response": {
                "id": 99998888,
                "status": "approved",
                "external_reference": "TEST-ORDER-REF-1",
                "payment_method_id": "webpay",
                "payment_type_id": "debit_card"
            }
        }

        processed_order = process_mercadopago_payment(99998888)

        self.assertIsNotNone(processed_order)
        self.assertEqual(processed_order.status, PlanSubscriptionOrder.Status.APPROVED)
        self.assertIsNotNone(processed_order.paid_at)

        # Verificar que el perfil del maestro se actualizó con el nuevo plan
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.plan, self.paid_plan)
        self.assertIsNotNone(self.profile.plan_expires_at)
        self.assertTrue(self.profile.plan_expires_at > timezone.now())

    def test_graphql_free_plan_activation(self):
        from graphene.test import Client as GrapheneClient
        from core.schema import schema

        query = f'''
        mutation {{
            createPlanSubscriptionPayment(planId: "{self.free_plan.id}") {{
                success
                requiresPayment
                message
                checkoutUrl
            }}
        }}
        '''
        client = GrapheneClient(schema)
        # Mock request context with authenticated user
        context = MagicMock()
        context.user = self.user
        result = client.execute(query, context=context)

        self.assertNotIn("errors", result)
        data = result["data"]["createPlanSubscriptionPayment"]
        self.assertTrue(data["success"])
        self.assertFalse(data["requiresPayment"])
        self.assertIsNone(data["checkoutUrl"])

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.plan, self.free_plan)
