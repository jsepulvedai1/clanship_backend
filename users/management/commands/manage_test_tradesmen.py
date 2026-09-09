from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from users.models import (
    User, Specialty, Tag, SubTag, ProfessionalProfile, SubscriptionPlan, UserAddress
)

# Constantes de identificación para los usuarios de prueba
TEST_USERNAME_PREFIX = "test_maestro_"
TEST_EMAIL_SUFFIX = "@test.clanship.cl"
TEST_PASSWORD = "ClanshipTest2026!"

# Datos realistas de los 12 maestros (Puerto Montt, Castro y Ancud)
TRADESMEN_DATA = [
    # -------------------------------------------------------------
    # PUERTO MONTT
    # -------------------------------------------------------------
    {
        "city": "Puerto Montt",
        "username": f"{TEST_USERNAME_PREFIX}pmontt_carpintero",
        "email": f"test.carlos.mansilla{TEST_EMAIL_SUFFIX}",
        "phone_number": "+56999010001",
        "first_name": "Carlos",
        "last_name": "Mansilla Paredes",
        "specialty": "Carpintería",
        "address": "Av. Los Notros 1420, Mirasol, Puerto Montt",
        "latitude": Decimal("-41.465200000"),
        "longitude": Decimal("-72.968400000"),
        "hourly_rate": Decimal("25000.00"),
        "rating": 4.9,
        "is_emergency": False,
        "bio": (
            "Maestro carpintero con más de 18 años de experiencia en Puerto Montt y alrededores. "
            "Especialista en ampliaciones de casas, instalación de puertas, ventanas, vigas a la vista, "
            "pisos flotantes y muebles a medida en maderas nativas. Trabajo garantizado y presupuestos sin compromiso."
        ),
        "tags": ["Carpintería", "Muebles a medida", "Pisos", "Terminaciones"],
    },
    {
        "city": "Puerto Montt",
        "username": f"{TEST_USERNAME_PREFIX}pmontt_gasfiter",
        "email": f"test.rodrigo.almonacid{TEST_EMAIL_SUFFIX}",
        "phone_number": "+56999010002",
        "first_name": "Rodrigo",
        "last_name": "Almonacid Soto",
        "specialty": "Gasfitería",
        "address": "Antonio Varas 680, Centro, Puerto Montt",
        "latitude": Decimal("-41.472100000"),
        "longitude": Decimal("-72.941200000"),
        "hourly_rate": Decimal("28000.00"),
        "rating": 5.0,
        "is_emergency": True,
        "bio": (
            "Gasfíter certificado SEC con amplia experiencia en emergencias y reparaciones residenciales. "
            "Detección de fugas de agua y gas, reparación e instalación de calefones, termos eléctricos, "
            "griferías y destape de alcantarillados. Atención de urgencias 24/7."
        ),
        "tags": ["Gasfitería", "Calefones", "Redes de Gas", "Alcantarillado"],
    },
    {
        "city": "Puerto Montt",
        "username": f"{TEST_USERNAME_PREFIX}pmontt_pintor",
        "email": f"test.patricio.cardenas{TEST_EMAIL_SUFFIX}",
        "phone_number": "+56999010003",
        "first_name": "Patricio",
        "last_name": "Cárdenas Vera",
        "specialty": "Pintura",
        "address": "Av. Marcelo Fourcade 2310, Valle Volcanes, Puerto Montt",
        "latitude": Decimal("-41.453800000"),
        "longitude": Decimal("-72.918500000"),
        "hourly_rate": Decimal("20000.00"),
        "rating": 4.8,
        "is_emergency": False,
        "bio": (
            "Pintor profesional con 12 años realizando trabajos de alta calidad en interiores y exteriores. "
            "Especialista en impermeabilización de fachadas y maderas contra el clima lluvioso del sur, "
            "tratamiento antihumedad, empastes y barnices. Prolijidad y limpieza absoluta."
        ),
        "tags": ["Pintura", "Terminaciones"],
    },
    {
        "city": "Puerto Montt",
        "username": f"{TEST_USERNAME_PREFIX}pmontt_lavado",
        "email": f"test.marcelo.vargas{TEST_EMAIL_SUFFIX}",
        "phone_number": "+56999010004",
        "first_name": "Marcelo",
        "last_name": "Vargas Gallardo",
        "specialty": "Lavado de Autos",
        "address": "Av. Juan Soler Manfredini 110, Costanera Pelluco, Puerto Montt",
        "latitude": Decimal("-41.482900000"),
        "longitude": Decimal("-72.912400000"),
        "hourly_rate": Decimal("35000.00"),
        "rating": 4.9,
        "is_emergency": False,
        "bio": (
            "Servicio móvil de detailing y lavado de autos a domicilio en Puerto Montt y Puerto Varas. "
            "Lavado full carrocería, limpieza profunda y desinfección a vapor de tapices, pulido de focos "
            "y aplicación de selladores cerámicos. Equipamiento autónomo de agua y energía."
        ),
        "tags": ["Lavado de Autos", "Detailing"],
    },

    # -------------------------------------------------------------
    # CASTRO (CHILOÉ)
    # -------------------------------------------------------------
    {
        "city": "Castro",
        "username": f"{TEST_USERNAME_PREFIX}castro_carpintero",
        "email": f"test.juan.haro{TEST_EMAIL_SUFFIX}",
        "phone_number": "+56999010005",
        "first_name": "Juan Bautista",
        "last_name": "Haro Chiguay",
        "specialty": "Carpintería",
        "address": "Calle Pedro Montt 580 (Sector Palafitos Gamboa), Castro, Chiloé",
        "latitude": Decimal("-42.482500000"),
        "longitude": Decimal("-73.774500000"),
        "hourly_rate": Decimal("24000.00"),
        "rating": 5.0,
        "is_emergency": False,
        "bio": (
            "Maestro carpintero chilote con tradición familiar. Especialista en construcción y restauración "
            "con tejuelas de ciprés y alerce, terrazas en madera tratada, revestimientos típicos chilotes "
            "y muebles rústicos a medida. Atención en Castro, Dalcahue y Chonchi."
        ),
        "tags": ["Carpintería", "Techumbres", "Terminaciones"],
    },
    {
        "city": "Castro",
        "username": f"{TEST_USERNAME_PREFIX}castro_gasfiter",
        "email": f"test.luis.carcamo{TEST_EMAIL_SUFFIX}",
        "phone_number": "+56999010006",
        "first_name": "Luis Alberto",
        "last_name": "Cárcamo Bahamonde",
        "specialty": "Gasfitería",
        "address": "Calle San Martín 420, Centro, Castro, Chiloé",
        "latitude": Decimal("-42.473900000"),
        "longitude": Decimal("-73.771200000"),
        "hourly_rate": Decimal("26000.00"),
        "rating": 4.8,
        "is_emergency": True,
        "bio": (
            "Gasfíter autorizado con servicio en toda la Isla Grande de Chiloé. Instalación de bombas "
            "de pozo profundo, termos solares y de gas, mantención y reparación de calefones, redes "
            "sanitarias rurales y urbanas. Rapidez y seriedad garantizada."
        ),
        "tags": ["Gasfitería", "Calefones", "Alcantarillado"],
    },
    {
        "city": "Castro",
        "username": f"{TEST_USERNAME_PREFIX}castro_pintor",
        "email": f"test.cristian.barrientos{TEST_EMAIL_SUFFIX}",
        "phone_number": "+56999010007",
        "first_name": "Cristián",
        "last_name": "Barrientos Oyarzún",
        "specialty": "Pintura",
        "address": "Ruta 5 Sur Km 4, Sector Nercón, Castro, Chiloé",
        "latitude": Decimal("-42.501500000"),
        "longitude": Decimal("-73.771800000"),
        "hourly_rate": Decimal("22000.00"),
        "rating": 4.9,
        "is_emergency": False,
        "bio": (
            "Pintor con 15 años de experiencia en la provincia de Chiloé. Protección especializada de "
            "maderas expuestas a humedad salina marina, pinturas hidrorrepelentes, aceites protectores "
            "y terminaciones de alto nivel en cabañas y casas residenciales."
        ),
        "tags": ["Pintura", "Terminaciones"],
    },
    {
        "city": "Castro",
        "username": f"{TEST_USERNAME_PREFIX}castro_lavado",
        "email": f"test.esteban.gomez{TEST_EMAIL_SUFFIX}",
        "phone_number": "+56999010008",
        "first_name": "Esteban",
        "last_name": "Gómez Macías",
        "specialty": "Lavado de Autos",
        "address": "Calle Galvarino Riveros 1250, Castro, Chiloé",
        "latitude": Decimal("-42.468200000"),
        "longitude": Decimal("-73.768900000"),
        "hourly_rate": Decimal("30000.00"),
        "rating": 4.7,
        "is_emergency": False,
        "bio": (
            "Detailing y estética vehicular a domicilio en Castro. Lavado cuidadoso de carrocería con champú "
            "pH neutro, lavado a presión de chasis para retirar barro y salitre invernal, descontaminado de pintura "
            "y limpieza profunda de interiores y tapicería."
        ),
        "tags": ["Lavado de Autos", "Detailing"],
    },

    # -------------------------------------------------------------
    # ANCUD (CHILOÉ)
    # -------------------------------------------------------------
    {
        "city": "Ancud",
        "username": f"{TEST_USERNAME_PREFIX}ancud_carpintero",
        "email": f"test.hector.nahuelquin{TEST_EMAIL_SUFFIX}",
        "phone_number": "+56999010009",
        "first_name": "Héctor René",
        "last_name": "Nahuelquín Téllez",
        "specialty": "Carpintería",
        "address": "Calle Almirante Latorre 450, Alto Caracoles, Ancud, Chiloé",
        "latitude": Decimal("-41.874500000"),
        "longitude": Decimal("-73.832000000"),
        "hourly_rate": Decimal("23000.00"),
        "rating": 4.9,
        "is_emergency": False,
        "bio": (
            "Carpintero con amplia experiencia en estructuras de madera y cubiertas. Reparación y refuerzo "
            "de techumbres para resistir los temporales de Chiloé, instalación de aislación térmica, "
            "puertas de exterior y ventanas termopanel. Trabajo fino y durable."
        ),
        "tags": ["Carpintería", "Techumbres", "Terminaciones"],
    },
    {
        "city": "Ancud",
        "username": f"{TEST_USERNAME_PREFIX}ancud_gasfiter",
        "email": f"test.jorge.conuecar{TEST_EMAIL_SUFFIX}",
        "phone_number": "+56999010010",
        "first_name": "Jorge Ignacio",
        "last_name": "Coñuecar Guineo",
        "specialty": "Gasfitería",
        "address": "Calle Prat 280, Centro, Ancud, Chiloé",
        "latitude": Decimal("-41.868200000"),
        "longitude": Decimal("-73.827800000"),
        "hourly_rate": Decimal("25000.00"),
        "rating": 4.8,
        "is_emergency": True,
        "bio": (
            "Gasfíter integral en Ancud y sectores rurales aledaños. Reparación inmediata de fugas de agua, "
            "mantención de calefones ionizados y tiro forzado, montaje de cañerías termofusionadas (PPR y cobre). "
            "Servicio rápido y garantizado."
        ),
        "tags": ["Gasfitería", "Calefones", "Redes de Gas"],
    },
    {
        "city": "Ancud",
        "username": f"{TEST_USERNAME_PREFIX}ancud_pintor",
        "email": f"test.claudio.millalonco{TEST_EMAIL_SUFFIX}",
        "phone_number": "+56999010011",
        "first_name": "Claudio Andrés",
        "last_name": "Millalonco Triviño",
        "specialty": "Pintura",
        "address": "Av. Salvador Allende 810, Costanera Pudeto, Ancud, Chiloé",
        "latitude": Decimal("-41.871500000"),
        "longitude": Decimal("-73.821000000"),
        "hourly_rate": Decimal("21000.00"),
        "rating": 4.8,
        "is_emergency": False,
        "bio": (
            "Pintor de interiores y exteriores con 10 años de trayectoria. Aplicación de pinturas vinílicas, "
            "esmaltes al agua, impermeabilizantes de muros exteriores, sellado de humedad y vitrificado de maderas. "
            "Excelente acabado y cumplimiento en plazos."
        ),
        "tags": ["Pintura", "Terminaciones"],
    },
    {
        "city": "Ancud",
        "username": f"{TEST_USERNAME_PREFIX}ancud_lavado",
        "email": f"test.matias.sanzana{TEST_EMAIL_SUFFIX}",
        "phone_number": "+56999010012",
        "first_name": "Matías",
        "last_name": "Sanzana Osorio",
        "specialty": "Lavado de Autos",
        "address": "Camino a Lechagua 350, Ancud, Chiloé",
        "latitude": Decimal("-41.859000000"),
        "longitude": Decimal("-73.855000000"),
        "hourly_rate": Decimal("28000.00"),
        "rating": 5.0,
        "is_emergency": False,
        "bio": (
            "CarWash móvil en Ancud. Servicio a domicilio con espuma activa (snow foam), limpieza de llantas, "
            "aspirado profundo, sanitización de tapices y aplicación de ceras hidrofóbicas para proteger tu vehículo "
            "del clima sureño."
        ),
        "tags": ["Lavado de Autos", "Detailing"],
    },
]

SPECIALTIES_CONFIG = {
    "Carpintería": {
        "color": "#8B5A2B",
        "synonyms": "carpintero, muebles, madera, tejuela, ampliacion, piso, vigas",
    },
    "Gasfitería": {
        "color": "#2980B9",
        "synonyms": "gasfiter, plomero, calefon, fugas, cañeria, termo, agua, gas",
    },
    "Pintura": {
        "color": "#E67E22",
        "synonyms": "pintor, esmalte, latex, fachada, barniz, humedad, empaste",
    },
    "Lavado de Autos": {
        "color": "#1ABC9C",
        "synonyms": "lavado de auto, carwash, detailing, tapiz, limpieza de auto, pulido",
    },
}


class Command(BaseCommand):
    help = "Crea, lista o elimina maestros de prueba hiperrealistas para Puerto Montt, Castro y Ancud."

    def add_arguments(self, parser):
        parser.add_argument(
            "--action",
            type=str,
            choices=["create", "delete", "list"],
            default="create",
            help="Acción a realizar: create (crear/actualizar), delete (eliminar todos los de prueba), list (listar).",
        )
        parser.add_argument(
            "--clean",
            action="store_true",
            help="Atajo equivalente a --action delete.",
        )

    def handle(self, *args, **options):
        action = "delete" if options["clean"] else options["action"]

        if action == "create":
            self.create_tradesmen()
        elif action == "delete":
            self.delete_tradesmen()
        elif action == "list":
            self.list_tradesmen()

    def get_or_create_specialty_and_tags(self):
        """Asegura que existan las especialidades y etiquetas necesarias."""
        specialty_map = {}
        for spec_name, spec_info in SPECIALTIES_CONFIG.items():
            spec, _ = Specialty.objects.get_or_create(
                name=spec_name,
                defaults={
                    "color": spec_info["color"],
                    "synonyms": spec_info["synonyms"],
                }
            )
            specialty_map[spec_name] = spec

        # Tags base
        tag_map = {}
        tags_to_ensure = [
            "Carpintería", "Gasfitería", "Pintura", "Lavado de Autos",
            "Detailing", "Calefones", "Redes de Gas", "Alcantarillado",
            "Muebles a medida", "Pisos", "Terminaciones", "Techumbres"
        ]
        for tag_name in tags_to_ensure:
            spec_rel = None
            if tag_name in ["Carpintería", "Muebles a medida", "Pisos", "Techumbres"]:
                spec_rel = specialty_map.get("Carpintería")
            elif tag_name in ["Gasfitería", "Calefones", "Redes de Gas", "Alcantarillado"]:
                spec_rel = specialty_map.get("Gasfitería")
            elif tag_name in ["Pintura", "Terminaciones"]:
                spec_rel = specialty_map.get("Pintura")
            elif tag_name in ["Lavado de Autos", "Detailing"]:
                spec_rel = specialty_map.get("Lavado de Autos")

            tag, _ = Tag.objects.get_or_create(
                name=tag_name,
                defaults={
                    "specialty": spec_rel,
                    "color": "#0B6E4F",
                    "synonyms": tag_name.lower(),
                }
            )
            tag_map[tag_name] = tag

        return specialty_map, tag_map

    @transaction.atomic
    def create_tradesmen(self):
        self.stdout.write(self.style.NOTICE("==> Creando/actualizando maestros de prueba realistas..."))
        specialty_map, tag_map = self.get_or_create_specialty_and_tags()

        # Plan de suscripción profesional o base
        plan = (
            SubscriptionPlan.objects.filter(name__icontains="Profesional").first()
            or SubscriptionPlan.objects.filter(name__icontains="Base").first()
            or SubscriptionPlan.objects.first()
        )

        created_count = 0
        updated_count = 0

        for item in TRADESMEN_DATA:
            user, created = User.objects.get_or_create(
                username=item["username"],
                defaults={
                    "email": item["email"],
                    "phone_number": item["phone_number"],
                    "first_name": item["first_name"],
                    "last_name": item["last_name"],
                    "user_type": User.UserType.PROFESSIONAL,
                    "address": item["address"],
                    "latitude": item["latitude"],
                    "longitude": item["longitude"],
                    "is_available": True,
                    "is_emergency": item["is_emergency"],
                }
            )

            # Si ya existía, actualizamos datos clave para asegurar consistencia
            user.email = item["email"]
            user.phone_number = item["phone_number"]
            user.first_name = item["first_name"]
            user.last_name = item["last_name"]
            user.user_type = User.UserType.PROFESSIONAL
            user.address = item["address"]
            user.latitude = item["latitude"]
            user.longitude = item["longitude"]
            user.is_available = True
            user.is_emergency = item["is_emergency"]
            user.set_password(TEST_PASSWORD)
            user.save()

            # Perfil profesional
            spec = specialty_map[item["specialty"]]
            profile, _ = ProfessionalProfile.objects.get_or_create(
                user=user,
                defaults={
                    "specialty": spec,
                    "plan": plan,
                    "bio": item["bio"],
                    "hourly_rate": item["hourly_rate"],
                    "rating": item["rating"],
                    "is_verified": True,
                    "verification_status": ProfessionalProfile.VerificationStatus.APPROVED,
                    "address": item["address"],
                    "latitude": item["latitude"],
                    "longitude": item["longitude"],
                    "service_radius": 35,
                }
            )

            profile.specialty = spec
            profile.plan = plan
            profile.bio = item["bio"]
            profile.hourly_rate = item["hourly_rate"]
            profile.rating = item["rating"]
            profile.is_verified = True
            profile.verification_status = ProfessionalProfile.VerificationStatus.APPROVED
            profile.address = item["address"]
            profile.latitude = item["latitude"]
            profile.longitude = item["longitude"]
            profile.service_radius = 35
            profile.save()

            # Asignar especialidad y tags
            profile.specialties.set([spec])
            assigned_tags = [tag_map[t] for t in item["tags"] if t in tag_map]
            if assigned_tags:
                profile.tags.set(assigned_tags)

            # Dirección de base en UserAddress
            UserAddress.objects.update_or_create(
                user=user,
                alias="Taller / Base",
                defaults={
                    "address": item["address"],
                    "latitude": item["latitude"],
                    "longitude": item["longitude"],
                }
            )

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(
                    f" [+] Creado: {user.get_full_name()} ({item['specialty']}) en {item['city']} -> {item['address']}"
                ))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(
                    f" [*] Actualizado: {user.get_full_name()} ({item['specialty']}) en {item['city']}"
                ))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"✓ Operación completada con éxito. Creados: {created_count}, Actualizados: {updated_count}. Total: {len(TRADESMEN_DATA)}"
        ))
        self.stdout.write(self.style.NOTICE(f"Contraseña asignada para todos los usuarios: '{TEST_PASSWORD}'"))
        self.stdout.write(self.style.NOTICE(
            f"Identificador para eliminación: username comienza con '{TEST_USERNAME_PREFIX}' o email termina en '{TEST_EMAIL_SUFFIX}'"
        ))

    @transaction.atomic
    def delete_tradesmen(self):
        self.stdout.write(self.style.WARNING("==> Buscando maestros de prueba para eliminar..."))

        users_to_delete = User.objects.filter(
            username__startswith=TEST_USERNAME_PREFIX
        ) | User.objects.filter(
            email__endswith=TEST_EMAIL_SUFFIX
        )

        total_users = users_to_delete.count()
        if total_users == 0:
            self.stdout.write(self.style.NOTICE("No se encontraron maestros de prueba con el prefijo o dominio especificado."))
            return

        self.stdout.write(f"Se encontraron {total_users} usuarios de prueba:")
        for u in users_to_delete:
            self.stdout.write(f" - {u.username} ({u.get_full_name()} | {u.email})")

        users_to_delete.delete()

        self.stdout.write(self.style.SUCCESS(f"✓ Se han eliminado exitosamente los {total_users} maestros de prueba y sus datos asociados."))

    def list_tradesmen(self):
        self.stdout.write(self.style.NOTICE("==> Listando maestros de prueba activos:"))

        users = User.objects.filter(
            username__startswith=TEST_USERNAME_PREFIX
        ).select_related("professional_profile__specialty").order_by("username")

        if not users.exists():
            self.stdout.write(self.style.WARNING("No hay maestros de prueba registrados actualmente."))
            self.stdout.write("Ejecuta 'python manage.py manage_test_tradesmen --action create' para crearlos.")
            return

        header = f"{'Ciudad':<15} | {'Nombre':<26} | {'Especialidad':<17} | {'Teléfono':<14} | {'Rating':<6} | {'Disp':<5}"
        self.stdout.write("-" * len(header))
        self.stdout.write(header)
        self.stdout.write("-" * len(header))

        for u in users:
            prof = getattr(u, 'professional_profile', None)
            spec_name = prof.specialty.name if (prof and prof.specialty) else "Sin espec."
            rating = f"{prof.rating}★" if prof else "N/A"
            disp = "Sí" if u.is_available else "No"
            city = "Desconocida"
            for d in TRADESMEN_DATA:
                if d["username"] == u.username:
                    city = d["city"]
                    break

            self.stdout.write(f"{city:<15} | {u.get_full_name():<26} | {spec_name:<17} | {u.phone_number or '':<14} | {rating:<6} | {disp:<5}")

        self.stdout.write("-" * len(header))
        self.stdout.write(self.style.SUCCESS(f"Total registrados: {users.count()}"))
