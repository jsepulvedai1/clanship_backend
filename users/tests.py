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

    def test_register_user_duplicate_phone_with_different_format_fails(self):
        from users.models import User
        User.objects.create_user(
            username="existing_variant@example.com",
            email="existing_variant@example.com",
            password="Password123!",
            phone_number="+56912345678"
        )
        # Register using variation without +56
        mutation = '''
        mutation {
          registerUser(
            email: "variant_user@example.com",
            password: "Password123!",
            firstName: "Carlos",
            lastName: "Soto",
            phoneNumber: "912345678"
          ) {
            success
          }
        }
        '''
        res = schema.execute(mutation)
        self.assertIsNotNone(res.errors)
        self.assertIn("El número de teléfono ya está registrado", str(res.errors))

    def test_check_user_existence_returns_user_message(self):
        from users.models import User
        User.objects.create_user(
            username="existing_check@example.com",
            email="existing_check@example.com",
            password="Password123!",
            phone_number="+56998877665"
        )
        query = '''
        query {
          checkUserExistence(phoneNumber: "+56998877665") {
            phoneExists
            emailExists
            userMessage
            message
          }
        }
        '''
        res = schema.execute(query)
        self.assertIsNone(res.errors)
        data = res.data['checkUserExistence']
        self.assertTrue(data['phoneExists'])
        self.assertIn("El número de teléfono ya está registrado", data['userMessage'])
        self.assertEqual(data['userMessage'], data['message'])

    def test_update_profile_empty_phone_does_not_erase_existing_phone(self):
        from users.models import User
        user = User.objects.create_user(
            username="preserve_phone@example.com",
            email="preserve_phone@example.com",
            password="Password123!",
            phone_number="+56911223344"
        )
        class MockContext:
            def __init__(self, user):
                self.user = user

        mutation = '''
        mutation {
          updateProfile(
            firstName: "Juan",
            lastName: "Perez",
            email: "preserve_phone@example.com",
            phoneNumber: "   "
          ) {
            success
            user {
              phoneNumber
            }
          }
        }
        '''
        res = schema.execute(mutation, context_value=MockContext(user))
        self.assertIsNone(res.errors)
        user.refresh_from_db()
        self.assertEqual(user.phone_number, "+56911223344")

    def test_user_clean_requires_phone_for_non_staff(self):
        from users.models import User
        from django.core.exceptions import ValidationError
        u = User(username="nophone@test.com", email="nophone@test.com", is_staff=False, is_superuser=False)
        with self.assertRaises(ValidationError):
            u.clean()


from unittest.mock import patch
from users.models import Specialty, SubTag, Tag, SubscriptionPlan

class SocialAuthAndOnboardingTestCase(TestCase):
    def setUp(self):
        self.initial_plan = SubscriptionPlan.objects.create(
            name="Plan Inicial",
            price=0,
            duration_days=30,
            max_completed_jobs=3
        )
        self.specialty = Specialty.objects.create(name="Gasfitería")
        self.tag = Tag.objects.create(name="Instalaciones", specialty=self.specialty)
        self.subtag = SubTag.objects.create(name="Calefones", tag=self.tag)

    @patch('core.firebase.verify_firebase_token')
    def test_social_auth_new_tradesman(self, mock_verify):
        from users.models import User
        mock_verify.return_value = {
            'uid': 'google_test_uid_123',
            'email': 'maestro_google@clanship.cl',
            'name': 'Pedro Maestro',
            'picture': 'https://example.com/avatar.jpg',
            'firebase': {'sign_in_provider': 'google.com'}
        }

        mutation = '''
        mutation {
          socialAuth(idToken: "mock_token_abc", provider: "GOOGLE", appType: "TRADESMAN") {
            token
            refreshToken
            isNewUser
            isProfileComplete
            user {
              email
              firstName
              lastName
              userType
              authProvider
              isProfileComplete
            }
          }
        }
        '''
        res = schema.execute(mutation)
        self.assertIsNone(res.errors)
        data = res.data['socialAuth']
        self.assertTrue(data['isNewUser'])
        self.assertFalse(data['isProfileComplete'])
        self.assertIsNotNone(data['token'])
        self.assertEqual(data['user']['email'], 'maestro_google@clanship.cl')
        self.assertEqual(data['user']['firstName'], 'Pedro')
        self.assertEqual(data['user']['lastName'], 'Maestro')
        self.assertEqual(data['user']['userType'], 'PROFESSIONAL')
        self.assertEqual(data['user']['authProvider'], 'GOOGLE')

        u = User.objects.get(email='maestro_google@clanship.cl')
        self.assertEqual(u.social_uid, 'google_test_uid_123')
        self.assertFalse(u.is_profile_complete)
        self.assertIsNotNone(u.professional_profile)
        self.assertEqual(u.professional_profile.plan.name, 'Plan Inicial')

    def test_complete_tradesman_onboarding_success(self):
        from users.models import User
        u = User.objects.create_user(
            username="onboarding_user@example.com",
            email="onboarding_user@example.com",
            first_name="Carlos",
            last_name="Valenzuela",
            auth_provider="GOOGLE",
            social_uid="uid_carlos",
            is_profile_complete=False
        )

        class MockContext:
            def __init__(self, user):
                self.user = user

        mutation = f'''
        mutation {{
          completeTradesmanOnboarding(
            phoneNumber: "+56977889900",
            specialtyId: "{self.specialty.id}",
            subtagIds: ["{self.subtag.id}"],
            address: "Providencia 1234, Santiago",
            latitude: -33.42,
            longitude: -70.61,
            serviceRadius: 15
          ) {{
            success
            user {{
              phoneNumber
              isProfileComplete
              professionalProfile {{
                isVerified
                serviceRadius
                specialty {{
                  id
                  name
                }}
              }}
            }}
          }}
        }}
        '''
        res = schema.execute(mutation, context_value=MockContext(u))
        self.assertIsNone(res.errors)
        data = res.data['completeTradesmanOnboarding']
        self.assertTrue(data['success'])
        self.assertEqual(data['user']['phoneNumber'], "+56977889900")
        self.assertTrue(data['user']['isProfileComplete'])
        self.assertEqual(data['user']['professionalProfile']['specialty']['name'], "Gasfitería")
        self.assertEqual(data['user']['professionalProfile']['serviceRadius'], 15)

        u.refresh_from_db()
        self.assertTrue(u.is_profile_complete)
        self.assertEqual(u.phone_number, "+56977889900")
        self.assertEqual(u.professional_profile.specialty, self.specialty)
        self.assertIn(self.subtag, u.professional_profile.subtags.all())

    def test_complete_tradesman_onboarding_duplicate_phone_fails(self):
        from users.models import User
        User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            phone_number="+56977889900"
        )
        u = User.objects.create_user(
            username="onboarding_user2@example.com",
            email="onboarding_user2@example.com",
            auth_provider="GOOGLE",
            social_uid="uid_carlos_2",
            is_profile_complete=False
        )

        class MockContext:
            def __init__(self, user):
                self.user = user

        mutation = f'''
        mutation {{
          completeTradesmanOnboarding(
            phoneNumber: "56977889900",
            specialtyId: "{self.specialty.id}"
          ) {{
            success
          }}
        }}
        '''
        res = schema.execute(mutation, context_value=MockContext(u))
        self.assertIsNotNone(res.errors)
        self.assertIn("ya está registrado", str(res.errors))

    def test_minimal_registration_email_flow(self):
        mutation = '''
        mutation {
          registerUser(
            email: "minimal_tradesman@clanship.cl",
            password: "SecretPassword123!",
            firstName: "Luis",
            lastName: "Gomez",
            userType: "PROFESSIONAL",
            minimalRegistration: true
          ) {
            success
            user {
              email
              isProfileComplete
              phoneNumber
            }
          }
        }
        '''
        res = schema.execute(mutation)
        self.assertIsNone(res.errors)
        data = res.data['registerUser']
        self.assertTrue(data['success'])
        self.assertFalse(data['user']['isProfileComplete'])
        self.assertIsNone(data['user']['phoneNumber'])
