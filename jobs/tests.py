from django.test import TestCase
from unittest.mock import patch
from django.contrib.auth import get_user_model
from users.models import Specialty, ProfessionalProfile, SystemSetting
from jobs.models import PublicJobRequest
from core.tasks import process_public_job_created_notifications, _calculate_distance_km

User = get_user_model()

class PublicJobPushNotificationTestCase(TestCase):
    def setUp(self):
        # Santiago Centro: aprox (-33.4489, -70.6693)
        self.specialty_gardening = Specialty.objects.create(name="Jardinería")
        self.specialty_electric = Specialty.objects.create(name="Electricidad")

        # Cliente
        self.customer = User.objects.create_user(
            username="cliente1",
            phone_number="+56911111111",
            user_type="CUSTOMER"
        )

        # Maestro cercano (Santiago, 5 km de distancia, radio 30 km)
        self.prof_near = User.objects.create_user(
            username="maestro_cercano",
            phone_number="+56922222222",
            user_type="PROFESSIONAL"
        )
        self.prof_near_profile = ProfessionalProfile.objects.create(
            user=self.prof_near,
            specialty=self.specialty_gardening,
            is_verified=True,
            verification_status="APPROVED",
            latitude=-33.4500,
            longitude=-70.6600,
            service_radius=30
        )

        # Maestro lejano (Rancagua / 100 km de distancia de Santiago, radio 30 km)
        # Rancagua aprox (-34.1701, -70.7407) ~ 85-90 km en línea recta
        # Talca aprox (-35.4264, -71.6554) ~ 240 km
        self.prof_far = User.objects.create_user(
            username="maestro_lejano_100km",
            phone_number="+56933333333",
            user_type="PROFESSIONAL"
        )
        self.prof_far_profile = ProfessionalProfile.objects.create(
            user=self.prof_far,
            specialty=self.specialty_gardening,
            is_verified=True,
            verification_status="APPROVED",
            latitude=-34.3000,
            longitude=-70.7400,
            service_radius=30
        )

        # Maestro de otra especialidad en Santiago
        self.prof_electric = User.objects.create_user(
            username="maestro_electricista",
            phone_number="+56944444444",
            user_type="PROFESSIONAL"
        )
        self.prof_electric_profile = ProfessionalProfile.objects.create(
            user=self.prof_electric,
            specialty=self.specialty_electric,
            is_verified=True,
            verification_status="APPROVED",
            latitude=-33.4500,
            longitude=-70.6600,
            service_radius=30
        )

    def test_distance_calculation(self):
        # Santiago a Talca o Rancagua
        dist_near = _calculate_distance_km(-33.4489, -70.6693, -33.4500, -70.6600)
        self.assertLess(dist_near, 5.0)

        dist_far = _calculate_distance_km(-33.4489, -70.6693, -34.3000, -70.7400)
        self.assertGreater(dist_far, 90.0)

    @patch('core.tasks.send_user_push_notification')
    def test_push_reaches_near_gardener_and_filters_far_gardener(self, mock_send_push):
        # Solicitud en Santiago Centro para Jardinería
        pub_req = PublicJobRequest.objects.create(
            customer=self.customer,
            specialty=self.specialty_gardening,
            title="Corte de pasto y poda de jardín",
            description="Jardín de 100m2",
            address="Santiago Centro",
            latitude=-33.4489,
            longitude=-70.6693,
            status=PublicJobRequest.Status.OPEN
        )

        # Ejecutar tarea de notificación
        process_public_job_created_notifications(pub_req.id)

        # Verificar qué usuarios recibieron la push
        notified_users = [call.kwargs['user'] for call in mock_send_push.call_args_list]

        # 1. El maestro cercano de jardinería debe recibir la push
        self.assertIn(self.prof_near, notified_users)

        # 2. El maestro a 100 km NO debe recibir la push (porque supera su service_radius de 30 km)
        self.assertNotIn(self.prof_far, notified_users)

        # 3. El electricista NO debe recibir la push (especialidad diferente)
        self.assertNotIn(self.prof_electric, notified_users)

    @patch('core.tasks.send_user_push_notification')
    def test_nationwide_mode_notifies_far_gardener(self, mock_send_push):
        # Activar modo nacional
        setting = SystemSetting.get_settings()
        setting.nationwide_coverage_mode = True
        setting.save()

        pub_req = PublicJobRequest.objects.create(
            customer=self.customer,
            specialty=self.specialty_gardening,
            title="Diseño de paisajismo online / nacional",
            description="Proyecto para jardín",
            address="Santiago Centro",
            latitude=-33.4489,
            longitude=-70.6693,
            status=PublicJobRequest.Status.OPEN
        )

        process_public_job_created_notifications(pub_req.id)

        notified_users = [call.kwargs['user'] for call in mock_send_push.call_args_list]

        # Con modo nacional, ambos jardineros reciben la push
        self.assertIn(self.prof_near, notified_users)
        self.assertIn(self.prof_far, notified_users)
        # El electricista sigue sin recibirla
        self.assertNotIn(self.prof_electric, notified_users)
