from django.test import TestCase, override_settings
from users.models import SystemSetting, User, UserAddress
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

    def test_complete_tradesman_onboarding_with_work_tags(self):
        from users.models import User
        u = User.objects.create_user(
            username="onboarding_tags@example.com",
            email="onboarding_tags@example.com",
            auth_provider="GOOGLE",
            social_uid="uid_tags_123",
            is_profile_complete=False
        )

        class MockContext:
            def __init__(self, user):
                self.user = user

        mutation = f'''
        mutation {{
          completeTradesmanOnboarding(
            phoneNumber: "+56911223344",
            specialtyIds: ["{self.specialty.id}"],
            tagIds: ["{self.tag.id}"],
            subtagIds: ["{self.subtag.id}"],
            address: "Santiago Centro",
            latitude: -33.45,
            longitude: -70.65,
            serviceRadius: 20
          ) {{
            success
            user {{
              phoneNumber
              isProfileComplete
              professionalProfile {{
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
        self.assertEqual(data['user']['phoneNumber'], "+56911223344")
        self.assertTrue(data['user']['isProfileComplete'])
        self.assertEqual(data['user']['professionalProfile']['specialty']['name'], "Gasfitería")

        u.refresh_from_db()
        self.assertTrue(u.is_profile_complete)
        self.assertIn(self.specialty, u.professional_profile.specialties.all())
        self.assertIn(self.tag, u.professional_profile.tags.all())
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

    def test_complete_tradesman_onboarding_missing_address_fails(self):
        from users.models import User
        u = User.objects.create_user(
            username="no_address@example.com",
            email="no_address@example.com",
            auth_provider="GOOGLE",
            social_uid="uid_no_address",
            is_profile_complete=False
        )

        class MockContext:
            def __init__(self, user):
                self.user = user

        mutation = f'''
        mutation {{
          completeTradesmanOnboarding(
            phoneNumber: "56988776655",
            specialtyId: "{self.specialty.id}",
            address: ""
          ) {{
            success
          }}
        }}
        '''
        res = schema.execute(mutation, context_value=MockContext(u))
        self.assertIsNotNone(res.errors)
        self.assertIn("zona de cobertura", str(res.errors).lower())

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

    def test_resume_incomplete_registration_flow(self):
        # 1. Crear un registro inicial incompleto
        reg_mutation = '''
        mutation {
          registerUser(
            email: "resume_test@clanship.cl",
            password: "MySecurePassword123!",
            firstName: "Pedro",
            lastName: "Perez",
            userType: "PROFESSIONAL",
            minimalRegistration: true
          ) {
            success
            user {
              isProfileComplete
            }
          }
        }
        '''
        res = schema.execute(reg_mutation)
        self.assertIsNone(res.errors)
        self.assertTrue(res.data['registerUser']['success'])

        # 2. Si el usuario cerró la app y vuelve a intentar registrarse con la misma contraseña:
        res2 = schema.execute(reg_mutation)
        self.assertIsNone(res2.errors)
        self.assertTrue(res2.data['registerUser']['success'])
        self.assertFalse(res2.data['registerUser']['user']['isProfileComplete'])

        # 3. Si intenta registrarse con contraseña errónea:
        wrong_pass_mutation = '''
        mutation {
          registerUser(
            email: "resume_test@clanship.cl",
            password: "WrongPassword123!",
            firstName: "Pedro",
            lastName: "Perez",
            userType: "PROFESSIONAL",
            minimalRegistration: true
          ) {
            success
          }
        }
        '''
        res3 = schema.execute(wrong_pass_mutation)
        self.assertIsNotNone(res3.errors)
        self.assertIn("registro está incompleto", str(res3.errors))

    def test_resolver_is_profile_complete_for_tradesman(self):
        from users.models import User, ProfessionalProfile
        user = User.objects.create_user(
            username="tradesman_incomplete@clanship.cl",
            email="tradesman_incomplete@clanship.cl",
            user_type="PROFESSIONAL",
            is_profile_complete=True # Marcado True por error o migración previa
        )
        ProfessionalProfile.objects.create(user=user, plan=self.initial_plan)

        class MockContext:
            def __init__(self, user):
                self.user = user

        query = '''
        query {
          me {
            isProfileComplete
          }
        }
        '''
        # Sin teléfono ni especialidad: debe ser False
        res = schema.execute(query, context_value=MockContext(user))
        self.assertIsNone(res.errors)
        self.assertFalse(res.data['me']['isProfileComplete'])

        # Agregamos teléfono pero aún sin especialidad: debe seguir siendo False
        user.phone_number = "+56912345678"
        user.save()
        res = schema.execute(query, context_value=MockContext(user))
        self.assertFalse(res.data['me']['isProfileComplete'])

        # Agregamos especialidad pero aún sin dirección: debe seguir siendo False
        prof = user.professional_profile
        prof.specialty = self.specialty
        prof.save()
        res = schema.execute(query, context_value=MockContext(user))
        self.assertFalse(res.data['me']['isProfileComplete'])

        # Agregamos dirección / zona de cobertura: ahora sí es True
        user.address = "Santiago, Chile"
        user.save()
        res = schema.execute(query, context_value=MockContext(user))
        self.assertTrue(res.data['me']['isProfileComplete'])

    def test_minimal_registration_client_and_onboarding_flow(self):
        from users.models import User, UserAddress
        mutation = '''
        mutation {
          registerUser(
            email: "minimal_client@clanship.cl",
            password: "SecretPassword123!",
            firstName: "Maria",
            lastName: "Soto",
            userType: "CUSTOMER",
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

        u = User.objects.get(email='minimal_client@clanship.cl')

        class MockContext:
            def __init__(self, user):
                self.user = user

        onboarding_mutation = '''
        mutation {
          completeClientOnboarding(
            address: "Av. Apoquindo 4500, Las Condes",
            latitude: -33.41,
            longitude: -70.58,
            phoneNumber: "+56912345678"
          ) {
            success
            user {
              address
              phoneNumber
              isProfileComplete
            }
          }
        }
        '''
        res2 = schema.execute(onboarding_mutation, context_value=MockContext(u))
        self.assertIsNone(res2.errors)
        onb_data = res2.data['completeClientOnboarding']
        self.assertTrue(onb_data['success'])
        self.assertTrue(onb_data['user']['isProfileComplete'])
        self.assertEqual(onb_data['user']['address'], "Av. Apoquindo 4500, Las Condes")
        self.assertEqual(onb_data['user']['phoneNumber'], "+56912345678")
        self.assertTrue(UserAddress.objects.filter(user=u, alias='Hogar').exists())

    def test_professional_validated_after_onboarding_and_verified_after_support_approval(self):
        """
        Verifica que al terminar su registro, el maestro queda 'validado' (isValidated=True)
        y operativo (puede activar su disponibilidad), pero NO 'verificado' (isVerified=False)
        hasta que soporte apruebe su documentación.
        """
        from users.models import User, ProfessionalProfile, Specialty

        spec = Specialty.objects.create(name='Gasfitería Test')
        u = User.objects.create_user(
            username='maestro_nuevo@clanship.cl',
            email='maestro_nuevo@clanship.cl',
            first_name='Maestro',
            last_name='Nuevo',
            user_type=User.UserType.PROFESSIONAL,
            is_profile_complete=False,
        )

        class MockContext:
            def __init__(self, user):
                self.user = user
                self.META = {}

        fast_onb = f'''
        mutation {{
          completeTradesmanOnboarding(
            phoneNumber: "+56977889900",
            specialtyIds: ["{spec.id}"],
            address: "Providencia, Santiago",
            latitude: -33.43,
            longitude: -70.61,
            serviceRadius: 15
          ) {{
            success
            user {{
              isProfileComplete
              isValidated
              isVerified
              professionalProfile {{
                isVerified
                verificationStatus
              }}
            }}
          }}
        }}
        '''
        res = schema.execute(fast_onb, context_value=MockContext(u))
        self.assertIsNone(res.errors)
        user_data = res.data['completeTradesmanOnboarding']['user']
        self.assertTrue(user_data['isProfileComplete'])
        self.assertTrue(user_data['isValidated'])
        self.assertFalse(user_data['isVerified'])
        self.assertFalse(user_data['professionalProfile']['isVerified'])
        self.assertEqual(user_data['professionalProfile']['verificationStatus'], 'PENDING')

        # El maestro validado (aunque no verificado) puede activar su disponibilidad
        u.refresh_from_db()
        avail_mut = '''
        mutation {
          updateAvailability(isAvailable: true) {
            success
            user {
              isAvailable
            }
          }
        }
        '''
        res_avail = schema.execute(avail_mut, context_value=MockContext(u))
        self.assertIsNone(res_avail.errors)
        self.assertTrue(res_avail.data['updateAvailability']['user']['isAvailable'])

        # Cuando soporte valida su documentación -> queda verificado (ticket azul)
        prof = u.professional_profile
        prof.verification_status = ProfessionalProfile.VerificationStatus.APPROVED
        prof.save()

        me_query = '''
        query {
          me {
            isValidated
            isVerified
            professionalProfile {
              isVerified
              verificationStatus
            }
          }
        }
        '''
        res_me = schema.execute(me_query, context_value=MockContext(u))
        self.assertIsNone(res_me.errors)
        me_data = res_me.data['me']
        self.assertTrue(me_data['isValidated'])
        self.assertTrue(me_data['isVerified'])
        self.assertTrue(me_data['professionalProfile']['isVerified'])
        self.assertEqual(me_data['professionalProfile']['verificationStatus'], 'APPROVED')


class WelcomeEmailTestCase(TestCase):
    def setUp(self):
        from users.models import WelcomeEmailTemplate
        self.templates = WelcomeEmailTemplate.ensure_defaults()
        self.admin_headers = {'HTTP_X_CLANSHIP_ADMIN': 'clanship_superadmin_2026'}

    def test_defaults_exist_and_differentiate_customer_and_professional(self):
        customer_tpl = self.templates['CUSTOMER']
        prof_tpl = self.templates['PROFESSIONAL']
        self.assertTrue(customer_tpl.is_active)
        self.assertTrue(prof_tpl.is_active)
        self.assertNotEqual(customer_tpl.subject, prof_tpl.subject)
        self.assertNotEqual(customer_tpl.body_html, prof_tpl.body_html)
        self.assertIn('Cliente', customer_tpl.get_user_type_display())
        self.assertIn('Maestro', prof_tpl.get_user_type_display())

    def test_render_welcome_email_escapes_html_in_user_fields(self):
        from users.welcome_emails import build_welcome_context, render_welcome_email
        u = User.objects.create(
            username='xss@test.cl',
            email='xss@test.cl',
            first_name='<script>alert(1)</script>',
            last_name='Perez',
            user_type=User.UserType.CUSTOMER,
        )
        rendered = render_welcome_email(self.templates['CUSTOMER'], build_welcome_context(u))
        self.assertNotIn('<script>alert(1)</script>', rendered['html'].lower())
        self.assertIn('&lt;script&gt;', rendered['html'].lower())
        self.assertIn('xss@test.cl', rendered['html'])

    @override_settings(RESEND_API_KEY='re_test_key')
    @patch('resend.Emails.send')
    def test_register_user_sends_differentiated_welcome_email_and_respects_toggle(self, mock_resend_send):
        mock_resend_send.return_value = {'id': 'msg_123'}

        # 1. Registro Cliente (activo)
        mutation_client = '''
        mutation {
          registerUser(
            email: "nuevo.cliente@test.cl",
            password: "Password123!",
            firstName: "Andrea",
            lastName: "Soto",
            phoneNumber: "+56911223344",
            userType: "CUSTOMER"
          ) {
            success
          }
        }
        '''
        with patch('users.welcome_emails.threading.Thread') as mock_thread:
            mock_thread.side_effect = lambda target, daemon=True: type('T', (), {'start': staticmethod(target)})()
            res = schema.execute(mutation_client)
        self.assertIsNone(res.errors)
        self.assertTrue(res.data['registerUser']['success'])

        welcome_calls = [
            call.args[0] for call in mock_resend_send.call_args_list
            if call.args[0].get('to') == ['nuevo.cliente@test.cl']
        ]
        self.assertEqual(len(welcome_calls), 1)
        self.assertIn('Andrea', welcome_calls[0]['subject'])
        self.assertIn('BIENVENIDO A CLANSHIP', welcome_calls[0]['html'])

        # 2. Registro Maestro (activo)
        mock_resend_send.reset_mock()
        mutation_prof = '''
        mutation {
          registerUser(
            email: "nuevo.maestro@test.cl",
            password: "Password123!",
            firstName: "Pedro",
            lastName: "Lagos",
            phoneNumber: "+56955667788",
            userType: "PROFESSIONAL"
          ) {
            success
          }
        }
        '''
        with patch('users.welcome_emails.threading.Thread') as mock_thread:
            mock_thread.side_effect = lambda target, daemon=True: type('T', (), {'start': staticmethod(target)})()
            res2 = schema.execute(mutation_prof)
        self.assertIsNone(res2.errors)
        self.assertTrue(res2.data['registerUser']['success'])

        welcome_prof_calls = [
            call.args[0] for call in mock_resend_send.call_args_list
            if call.args[0].get('to') == ['nuevo.maestro@test.cl']
        ]
        self.assertEqual(len(welcome_prof_calls), 1)
        self.assertIn('Maestros Clanship', welcome_prof_calls[0]['subject'])
        self.assertIn('COMUNIDAD DE MAESTROS', welcome_prof_calls[0]['html'])

        # 3. Desactivar plantilla de Cliente -> no debe enviarse correo de bienvenida al cliente
        mock_resend_send.reset_mock()
        tpl_cust = self.templates['CUSTOMER']
        tpl_cust.is_active = False
        tpl_cust.save()

        mutation_client_2 = '''
        mutation {
          registerUser(
            email: "cliente.apagado@test.cl",
            password: "Password123!",
            firstName: "Luis",
            lastName: "Mora",
            phoneNumber: "+56999887766",
            userType: "CUSTOMER"
          ) {
            success
          }
        }
        '''
        with patch('users.welcome_emails.threading.Thread') as mock_thread:
            mock_thread.side_effect = lambda target, daemon=True: type('T', (), {'start': staticmethod(target)})()
            res3 = schema.execute(mutation_client_2)
        self.assertIsNone(res3.errors)
        disabled_calls = [
            call.args[0] for call in mock_resend_send.call_args_list
            if call.args[0].get('to') == ['cliente.apagado@test.cl']
        ]
        self.assertEqual(len(disabled_calls), 0)

    @override_settings(RESEND_API_KEY='re_test_key')
    @patch('resend.Emails.send')
    @patch('core.firebase.verify_firebase_token')
    def test_social_auth_sends_welcome_email_only_for_new_user(self, mock_verify, mock_resend_send):
        mock_resend_send.return_value = {'id': 'msg_social_1'}
        mock_verify.return_value = {
            'uid': 'google_welcome_uid_1',
            'email': 'social.maestro@test.cl',
            'name': 'Javiera Núñez',
            'firebase': {'sign_in_provider': 'google.com'},
        }
        mutation = '''
        mutation {
          socialAuth(idToken: "tok_123", provider: "GOOGLE", appType: "TRADESMAN") {
            success
            isNewUser
          }
        }
        '''
        with patch('users.welcome_emails.threading.Thread') as mock_thread:
            mock_thread.side_effect = lambda target, daemon=True: type('T', (), {'start': staticmethod(target)})()
            res = schema.execute(mutation)
        self.assertIsNone(res.errors)
        self.assertTrue(res.data['socialAuth']['isNewUser'])
        self.assertEqual(mock_resend_send.call_count, 1)
        self.assertEqual(mock_resend_send.call_args[0][0]['to'], ['social.maestro@test.cl'])
        self.assertIn('COMUNIDAD DE MAESTROS', mock_resend_send.call_args[0][0]['html'])

        # Segundo login no debe reenviar bienvenida
        mock_resend_send.reset_mock()
        with patch('users.welcome_emails.threading.Thread') as mock_thread:
            mock_thread.side_effect = lambda target, daemon=True: type('T', (), {'start': staticmethod(target)})()
            res2 = schema.execute(mutation)
        self.assertIsNone(res2.errors)
        self.assertFalse(res2.data['socialAuth']['isNewUser'])
        self.assertEqual(mock_resend_send.call_count, 0)

    @override_settings(RESEND_API_KEY='re_test_key')
    @patch('resend.Emails.send')
    def test_admin_welcome_email_api_endpoints(self, mock_resend_send):
        import json
        mock_resend_send.return_value = {'id': 'msg_test_999'}

        # Sin permiso admin -> 403
        unauth = self.client.get('/api/v1/admin/welcome-emails/')
        self.assertEqual(unauth.status_code, 403)

        # GET listado
        res_get = self.client.get('/api/v1/admin/welcome-emails/', **self.admin_headers)
        self.assertEqual(res_get.status_code, 200)
        data = res_get.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['templates']), 2)

        # POST actualizar plantilla CUSTOMER completamente
        payload = {
            'is_active': True,
            'sender_name': 'Clanship VIP',
            'reply_to': 'hola@clanship.cl',
            'subject': 'Hola {first_name}, asunto editado',
            'header_title': 'Título editado para {first_name}',
            'body_html': '<p>Contenido completamente editado para {email}.</p>',
            'cta_text': 'Entrar ahora',
            'cta_url': 'https://clanship.cl/app',
            'footer_text': 'Pie editado {year}',
        }
        res_post = self.client.post(
            '/api/v1/admin/welcome-emails/CUSTOMER/',
            data=json.dumps(payload),
            content_type='application/json',
            **self.admin_headers,
        )
        self.assertEqual(res_post.status_code, 200)
        updated = res_post.json()['template']
        self.assertEqual(updated['sender_name'], 'Clanship VIP')
        self.assertEqual(updated['subject'], 'Hola {first_name}, asunto editado')
        self.assertIn('Contenido completamente editado', updated['preview_html'])

        # POST toggle activar/desactivar
        res_toggle = self.client.post(
            '/api/v1/admin/welcome-emails/CUSTOMER/toggle/',
            data=json.dumps({}),
            content_type='application/json',
            **self.admin_headers,
        )
        self.assertEqual(res_toggle.status_code, 200)
        self.assertFalse(res_toggle.json()['is_active'])

        # POST preview sin guardar
        res_prev = self.client.post(
            '/api/v1/admin/welcome-emails/PROFESSIONAL/preview/',
            data=json.dumps({'subject': 'Borrador {first_name}', 'body_html': '<p>Texto borrador</p>'}),
            content_type='application/json',
            **self.admin_headers,
        )
        self.assertEqual(res_prev.status_code, 200)
        self.assertEqual(res_prev.json()['preview']['subject'], 'Borrador Matías')
        self.assertIn('Texto borrador', res_prev.json()['preview']['html'])

        # POST enviar correo de prueba
        res_test = self.client.post(
            '/api/v1/admin/welcome-emails/PROFESSIONAL/test/',
            data=json.dumps({'to_email': 'gestor@clanship.cl'}),
            content_type='application/json',
            **self.admin_headers,
        )
        self.assertEqual(res_test.status_code, 200)
        self.assertTrue(res_test.json()['success'])
        self.assertEqual(mock_resend_send.call_args[0][0]['to'], ['gestor@clanship.cl'])

        # POST reset
        res_reset = self.client.post(
            '/api/v1/admin/welcome-emails/CUSTOMER/reset/',
            data=json.dumps({}),
            content_type='application/json',
            **self.admin_headers,
        )
        self.assertEqual(res_reset.status_code, 200)
        self.assertIn('Encuentra maestros de confianza', res_reset.json()['template']['subject'])



