import base64
import tempfile
from types import SimpleNamespace

from django.test import TestCase, override_settings

from core.schema import schema
from users.models import Municipality, ProfessionalProfile, User


# 1x1 PNG transparente mínimo en base64 para pruebas de subida de logo
SAMPLE_PNG_B64 = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _make_request(user=None, admin_header=False):
    meta = {}
    if admin_header:
        meta["HTTP_X_CLANSHIP_ADMIN"] = "clanship_superadmin_2026"
    return SimpleNamespace(
        user=user or SimpleNamespace(is_anonymous=True),
        META=meta,
        build_absolute_uri=lambda path: f"https://api.clanship.cl{path}",
    )


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class MunicipalityGraphQLTestCase(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="admin_muni",
            email="admin_muni@test.com",
            password="password123",
            user_type=User.UserType.ADMIN,
            is_staff=True,
        )
        self.tradesman_user = User.objects.create_user(
            username="maestro_muni",
            email="maestro_muni@test.com",
            password="password123",
            user_type=User.UserType.PROFESSIONAL,
            first_name="Javier",
            last_name="Sepulveda",
        )
        self.profile = ProfessionalProfile.objects.create(user=self.tradesman_user)

    def test_create_update_assign_unlink_and_me_query(self):
        admin_ctx = _make_request(user=self.admin_user, admin_header=True)

        # 1. Crear municipalidad con logo en base64
        create_mutation = """
        mutation CreateMuni($name: String!, $code: String!, $logoBase64: String, $isActive: Boolean) {
          createMunicipality(name: $name, code: $code, logoBase64: $logoBase64, isActive: $isActive) {
            success
            message
            municipality {
              id
              name
              code
              logoUrl
              isActive
            }
          }
        }
        """
        res = schema.execute(
            create_mutation,
            variables={
                "name": "Municipalidad de Santiago",
                "code": "stgo",
                "logoBase64": SAMPLE_PNG_B64,
                "isActive": True,
            },
            context_value=admin_ctx,
        )
        self.assertIsNone(res.errors)
        data = res.data["createMunicipality"]
        self.assertTrue(data["success"])
        muni = data["municipality"]
        self.assertEqual(muni["name"], "Municipalidad de Santiago")
        self.assertEqual(muni["code"], "STGO")
        self.assertTrue(muni["isActive"])
        self.assertIsNotNone(muni["logoUrl"])
        self.assertIn("/media/municipalities/", muni["logoUrl"])
        muni_id = muni["id"]

        # 2. Rechazar código duplicado
        dup_res = schema.execute(
            create_mutation,
            variables={"name": "Otra", "code": "STGO"},
            context_value=admin_ctx,
        )
        self.assertIsNotNone(dup_res.errors)

        # 3. Asociar maestro a la municipalidad
        assign_mutation = """
        mutation AssignMuni($userId: ID!, $municipalityId: ID!) {
          assignTradesmanMunicipality(userId: $userId, municipalityId: $municipalityId) {
            success
            message
            professionalProfile {
              id
              municipality {
                id
                name
                code
                logoUrl
              }
            }
          }
        }
        """
        assign_res = schema.execute(
            assign_mutation,
            variables={"userId": str(self.tradesman_user.id), "municipalityId": muni_id},
            context_value=admin_ctx,
        )
        self.assertIsNone(assign_res.errors)
        self.assertTrue(assign_res.data["assignTradesmanMunicipality"]["success"])
        self.assertEqual(
            assign_res.data["assignTradesmanMunicipality"]["professionalProfile"]["municipality"]["code"],
            "STGO",
        )

        # 4. Consultar perfil del maestro (`me`) y verificar municipality { id name code logoUrl }
        me_query = """
        query {
          me {
            id
            professionalProfile {
              municipality {
                id
                name
                code
                logoUrl
              }
            }
          }
        }
        """
        fresh_tradesman = User.objects.select_related("professional_profile__municipality").get(
            pk=self.tradesman_user.pk
        )
        tradesman_ctx = _make_request(user=fresh_tradesman)
        me_res = schema.execute(me_query, context_value=tradesman_ctx)
        self.assertIsNone(me_res.errors)
        me_muni = me_res.data["me"]["professionalProfile"]["municipality"]
        self.assertEqual(me_muni["id"], muni_id)
        self.assertEqual(me_muni["name"], "Municipalidad de Santiago")
        self.assertEqual(me_muni["code"], "STGO")
        self.assertIsNotNone(me_muni["logoUrl"])

        # 5. Actualizar municipalidad (estado y nombre)
        update_mutation = """
        mutation UpdateMuni($id: ID!, $name: String, $isActive: Boolean) {
          updateMunicipality(id: $id, name: $name, isActive: $isActive) {
            success
            municipality {
              id
              name
              code
              isActive
            }
          }
        }
        """
        upd_res = schema.execute(
            update_mutation,
            variables={"id": muni_id, "name": "Ilustre Municipalidad de Santiago", "isActive": False},
            context_value=admin_ctx,
        )
        self.assertIsNone(upd_res.errors)
        self.assertEqual(upd_res.data["updateMunicipality"]["municipality"]["name"], "Ilustre Municipalidad de Santiago")
        self.assertFalse(upd_res.data["updateMunicipality"]["municipality"]["isActive"])

        # 6. Desvincular maestro
        unlink_mutation = """
        mutation UnlinkMuni($userId: ID!) {
          unlinkTradesmanMunicipality(userId: $userId) {
            success
            professionalProfile {
              municipality {
                id
              }
            }
          }
        }
        """
        unlink_res = schema.execute(
            unlink_mutation,
            variables={"userId": str(self.tradesman_user.id)},
            context_value=admin_ctx,
        )
        self.assertIsNone(unlink_res.errors)
        self.assertTrue(unlink_res.data["unlinkTradesmanMunicipality"]["success"])
        self.assertIsNone(unlink_res.data["unlinkTradesmanMunicipality"]["professionalProfile"]["municipality"])

    def test_municipality_delete_sets_null_on_professional_profile(self):
        muni = Municipality.objects.create(name="Municipalidad de Providencia", code="PROV", is_active=True)
        self.profile.municipality = muni
        self.profile.save(update_fields=["municipality"])

        muni.delete()
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.municipality)

    def test_differentiated_banner_flow_general_municipality_mixed(self):
        from django.test import Client
        from users.models import Banner

        stgo = Municipality.objects.create(
            name="Municipalidad de Santiago",
            code="STGO",
            is_active=True,
            banner_display_mode=Municipality.BannerDisplayMode.GENERAL,
        )
        prov = Municipality.objects.create(
            name="Municipalidad de Providencia",
            code="PROV",
            is_active=True,
            banner_display_mode=Municipality.BannerDisplayMode.MIXED,
        )

        b_general = Banner.objects.create(
            title="Banner General Clanship",
            app_type=Banner.AppType.TRADESMAN,
            municipality=None,
            is_active=True,
            display_order=1,
        )
        b_stgo = Banner.objects.create(
            title="Banner Exclusivo Santiago",
            app_type=Banner.AppType.TRADESMAN,
            municipality=stgo,
            is_active=True,
            display_order=1,
        )
        b_prov = Banner.objects.create(
            title="Banner Exclusivo Providencia",
            app_type=Banner.AppType.TRADESMAN,
            municipality=prov,
            is_active=True,
            display_order=1,
        )

        client = Client()

        # 1. Maestro SIN municipalidad (o versión antigua): solo ve banner general
        res_unlinked = client.get("/api/v1/banners/?app_type=TRADESMAN").json()
        self.assertEqual([b["id"] for b in res_unlinked["banners"]], [b_general.id])
        self.assertEqual(res_unlinked["banner_display_mode"], "GENERAL")

        # 2. Maestro de Santiago en modo GENERAL: solo ve banner general
        res_gen = client.get(f"/api/v1/banners/?app_type=TRADESMAN&municipality_id={stgo.id}").json()
        self.assertEqual([b["id"] for b in res_gen["banners"]], [b_general.id])
        self.assertEqual(res_gen["banner_display_mode"], "GENERAL")

        # 3. Maestro de Santiago en modo MUNICIPALITY: solo ve banner de Santiago (ni general ni Providencia)
        stgo.banner_display_mode = Municipality.BannerDisplayMode.MUNICIPALITY
        stgo.save(update_fields=["banner_display_mode"])
        res_muni = client.get(f"/api/v1/banners/?app_type=TRADESMAN&municipality_id={stgo.id}").json()
        self.assertEqual([b["id"] for b in res_muni["banners"]], [b_stgo.id])
        self.assertEqual(res_muni["banner_display_mode"], "MUNICIPALITY")

        # 4. Maestro de Santiago en modo MIXED: ve ambos (primero Santiago, luego General; nunca Providencia)
        stgo.banner_display_mode = Municipality.BannerDisplayMode.MIXED
        stgo.save(update_fields=["banner_display_mode"])
        res_mixed = client.get(f"/api/v1/banners/?app_type=TRADESMAN&municipality_id={stgo.id}").json()
        self.assertEqual([b["id"] for b in res_mixed["banners"]], [b_stgo.id, b_general.id])
        self.assertEqual(res_mixed["banner_display_mode"], "MIXED")

        # 5. Maestro de Providencia en modo MIXED: ve Providencia + General (nunca Santiago)
        res_prov = client.get(f"/api/v1/banners/?app_type=TRADESMAN&municipality_id={prov.id}").json()
        self.assertEqual([b["id"] for b in res_prov["banners"]], [b_prov.id, b_general.id])

        # 6. Cliente siempre ve solo general aunque pase municipality_id
        b_all = Banner.objects.create(
            title="Banner General Ambas Apps",
            app_type=Banner.AppType.ALL,
            municipality=None,
            is_active=True,
            display_order=2,
        )
        res_client = client.get(f"/api/v1/banners/?app_type=CLIENT&municipality_id={stgo.id}").json()
        self.assertEqual([b["id"] for b in res_client["banners"]], [b_all.id])

        # 7. Municipalidad inactiva cae a modo GENERAL
        stgo.is_active = False
        stgo.save(update_fields=["is_active"])
        res_inactive = client.get(f"/api/v1/banners/?app_type=TRADESMAN&municipality_id={stgo.id}").json()
        self.assertEqual([b["id"] for b in res_inactive["banners"]], [b_general.id, b_all.id])

