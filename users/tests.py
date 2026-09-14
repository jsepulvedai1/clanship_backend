from django.test import TestCase
from users.models import SystemSetting
from core.schema import schema

class SubscriptionVersionBlockingTestCase(TestCase):
    def setUp(self):
        self.setting = SystemSetting.get_settings()

    def test_version_blocking_logic(self):
        self.setting.subscriptions_enabled_ios = True
        self.setting.subscriptions_min_version_ios = "1.0.5"
        self.setting.subscriptions_blocked_versions_ios = "1.0.6, 1.0.7"
        self.setting.save()

        # Older than min_version
        self.assertFalse(self.setting.is_subscription_enabled_for_version('ios', '1.0.4'))
        # Equal to min_version
        self.assertTrue(self.setting.is_subscription_enabled_for_version('ios', '1.0.5'))
        self.assertTrue(self.setting.is_subscription_enabled_for_version('ios', '1.0.5+10'))
        # Blocked version
        self.assertFalse(self.setting.is_subscription_enabled_for_version('ios', '1.0.6'))
        self.assertFalse(self.setting.is_subscription_enabled_for_version('ios', '1.0.6+99'))
        self.assertFalse(self.setting.is_subscription_enabled_for_version('ios', '1.0.7'))
        # Newer allowed version
        self.assertTrue(self.setting.is_subscription_enabled_for_version('ios', '1.0.8'))

    def test_master_switch_disabled(self):
        self.setting.subscriptions_enabled_ios = False
        self.setting.save()
        self.assertFalse(self.setting.is_subscription_enabled_for_version('ios', '1.0.8'))

    def test_graphql_app_config_query(self):
        self.setting.subscriptions_enabled_ios = True
        self.setting.subscriptions_min_version_ios = "1.0.5"
        self.setting.subscriptions_blocked_versions_ios = "1.0.6"
        self.setting.save()

        q_blocked = '''
        query {
          appConfig(platform: "ios", appVersion: "1.0.6") {
            subscriptionsEnabledIos
            isSubscriptionsEnabled
            subscriptionsBlockedVersionsIos
            subscriptionsMinVersionIos
          }
        }
        '''
        res_blocked = schema.execute(q_blocked)
        self.assertFalse(res_blocked.data['appConfig']['subscriptionsEnabledIos'])
        self.assertFalse(res_blocked.data['appConfig']['isSubscriptionsEnabled'])
        self.assertEqual(res_blocked.data['appConfig']['subscriptionsBlockedVersionsIos'], "1.0.6")

        q_allowed = '''
        query {
          appConfig(platform: "ios", appVersion: "1.0.8") {
            subscriptionsEnabledIos
            isSubscriptionsEnabled
          }
        }
        '''
        res_allowed = schema.execute(q_allowed)
        self.assertTrue(res_allowed.data['appConfig']['subscriptionsEnabledIos'])
        self.assertTrue(res_allowed.data['appConfig']['isSubscriptionsEnabled'])


class NationwideCoverageTestCase(TestCase):
    def setUp(self):
        from users.models import User, ProfessionalProfile
        self.setting = SystemSetting.get_settings()
        self.setting.nationwide_coverage_mode = False
        self.setting.save()

        # Maestro en Santiago (lat -33.4489, lon -70.6693) con radio de 10 km
        self.prof_user = User.objects.create_user(
            username='maestro_santiago',
            email='maestro_santiago@test.com',
            password='password123',
            user_type=User.UserType.PROFESSIONAL,
            is_available=True,
            first_name='Juan',
            last_name='Perez'
        )
        self.profile = ProfessionalProfile.objects.create(
            user=self.prof_user,
            service_radius=10,
            latitude=-33.4489,
            longitude=-70.6693,
            is_verified=True
        )

    def test_nationwide_coverage_flag_detection(self):
        self.setting.nationwide_coverage_mode = False
        self.setting.save()
        self.assertFalse(SystemSetting.is_nationwide_coverage_active())

        self.setting.nationwide_coverage_mode = True
        self.setting.save()
        self.assertTrue(SystemSetting.is_nationwide_coverage_active())

    def test_search_nearby_professionals_nationwide(self):
        # Consulta desde Valparaíso (~100 km de distancia de Santiago)
        # Lat: -33.0472, Lon: -71.6127
        query = '''
        query {
          nearbyProfessionals(latitude: -33.0472, longitude: -71.6127) {
            id
            username
            distance
          }
        }
        '''
        # 1. Con modo nacional desactivado: No debe retornar al maestro (100 km > 10 km)
        self.setting.nationwide_coverage_mode = False
        self.setting.save()
        res = schema.execute(query)
        self.assertIsNone(res.errors)
        self.assertEqual(len(res.data['nearbyProfessionals']), 0)

        # 2. Con modo nacional activado: Debe retornar al maestro de Santiago
        self.setting.nationwide_coverage_mode = True
        self.setting.save()
        res = schema.execute(query)
        self.assertIsNone(res.errors)
        self.assertEqual(len(res.data['nearbyProfessionals']), 1)
        self.assertEqual(res.data['nearbyProfessionals'][0]['username'], 'maestro_santiago')
        # La distancia debe ser calculada y superior a 90 km
        self.assertGreater(res.data['nearbyProfessionals'][0]['distance'], 90.0)

    def test_create_job_radius_validation_nationwide(self):
        from users.models import User
        from django.test import RequestFactory
        from jobs.schema import CreateJob
        import datetime

        # Cliente en Valparaíso (~100 km de distancia)
        customer = User.objects.create_user(
            username='cliente_valpo',
            email='cliente_valpo@test.com',
            password='password123',
            user_type=User.UserType.CUSTOMER,
            latitude=-33.0472,
            longitude=-71.6127
        )

        rf = RequestFactory()
        request = rf.post('/graphql/')
        request.user = customer

        mutation_gql = '''
        mutation {
          createJob(
            professionalId: %d,
            scheduledDate: "%s",
            scheduledTime: "10:00:00",
            description: "Reparación techo",
            agreedPrice: "50000",
            address: "Valparaíso centro"
          ) {
            job {
              id
              status
            }
          }
        }
        ''' % (self.prof_user.id, (datetime.date.today() + datetime.timedelta(days=1)).isoformat())

        # 1. Modo nacional apagado: debe fallar con error de radio
        self.setting.nationwide_coverage_mode = False
        self.setting.save()
        res_fail = schema.execute(mutation_gql, context_value=request)
        self.assertIsNotNone(res_fail.errors)
        self.assertIn("radio de cobertura", str(res_fail.errors[0]))

        # 2. Modo nacional encendido: debe crear el trabajo exitosamente
        self.setting.nationwide_coverage_mode = True
        self.setting.save()
        res_ok = schema.execute(mutation_gql, context_value=request)
        self.assertIsNone(res_ok.errors)
        self.assertIsNotNone(res_ok.data['createJob']['job']['id'])


class RegisterUserPhoneValidationTestCase(TestCase):
    def test_register_user_missing_phone_fails(self):
        mutation = '''
        mutation {
          registerUser(
            email: "test_nophone@example.com",
            password: "Password123!",
            firstName: "Juan",
            lastName: "Perez",
            phoneNumber: ""
          ) {
            success
          }
        }
        '''
        res = schema.execute(mutation)
        self.assertIsNotNone(res.errors)
        self.assertIn("El número de teléfono es obligatorio", str(res.errors))

    def test_register_user_duplicate_phone_fails(self):
        from users.models import User
        User.objects.create_user(
            username="existing@example.com",
            email="existing@example.com",
            password="Password123!",
            phone_number="+56912345678"
        )
        mutation = '''
        mutation {
          registerUser(
            email: "new_user@example.com",
            password: "Password123!",
            firstName: "Pedro",
            lastName: "Gomez",
            phoneNumber: "+56912345678"
          ) {
            success
          }
        }
        '''
        res = schema.execute(mutation)
        self.assertIsNotNone(res.errors)
        self.assertIn("El número de teléfono ya está registrado", str(res.errors))

    def test_register_user_with_valid_phone_succeeds(self):
        mutation = '''
        mutation {
          registerUser(
            email: "valid_user@example.com",
            password: "Password123!",
            firstName: "Maria",
            lastName: "Lopez",
            phoneNumber: "+56987654321"
          ) {
            success
            user {
              id
              phoneNumber
            }
          }
        }
        '''
        res = schema.execute(mutation)
        self.assertIsNone(res.errors)
        self.assertTrue(res.data['registerUser']['success'])
        self.assertEqual(res.data['registerUser']['user']['phoneNumber'], "+56987654321")




