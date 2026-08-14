import uuid
import graphene
from graphene_django import DjangoObjectType
from .models import User, Specialty, ProfessionalProfile, Tag, SubTag, ProfessionalPhoto, ProfessionalDocument, SubscriptionPlan, UserAddress, PasswordResetOTP, UserDevice, SystemSetting
import graphql_jwt
from graphql_jwt.decorators import login_required
from decimal import Decimal
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail


class UserAddressType(DjangoObjectType):
    class Meta:
        model = UserAddress
        fields = ("id", "address", "latitude", "longitude", "alias")


class UserType(DjangoObjectType):
    avatar_url = graphene.String()
    active_jobs = graphene.Int()
    completed_jobs = graphene.Int()
    scheduled_jobs = graphene.Int()
    rejected_jobs = graphene.Int()
    reviews_count = graphene.Int()
    is_favorite = graphene.Boolean()
    saved_addresses = graphene.List(UserAddressType)
    distance = graphene.Float()
    is_validated = graphene.Boolean()

    class Meta:
        model = User
        fields = (
            "id", "username", "email", "phone_number", "user_type", 
            "avatar", "latitude", "longitude", "address", 
            "is_available", "is_emergency", "professional_profile", "first_name", "last_name",
            "active_jobs", "completed_jobs", "scheduled_jobs", "rejected_jobs", "reviews_count",
            "is_favorite", "fcm_token", "saved_addresses", "is_validated"
        )

    def resolve_is_validated(self, info):
        prof = getattr(self, 'professional_profile', None)
        if prof:
            return prof.is_verified
        return True

    def resolve_distance(self, info):
        return getattr(self, 'distance', 0.0)

    def resolve_saved_addresses(self, info):
        return self.saved_addresses.all()

    def resolve_is_favorite(self, info):
        user = info.context.user
        if user.is_anonymous:
            return False
        return user.favorite_professionals.filter(id=self.id).exists()

    def resolve_avatar_url(self, info):
        if self.avatar:
            return info.context.build_absolute_uri(self.avatar.url)
        return None

    def resolve_first_name(self, info):
        if self.first_name:
            return self.first_name.strip().title()
        return ""

    def resolve_last_name(self, info):
        if self.last_name:
            return self.last_name.strip().title()
        return ""

    def resolve_active_jobs(self, info):
        from jobs.models import Job
        from django.db.models import Q
        return Job.objects.filter(
            Q(customer=self) | Q(professional=self),
            status=Job.Status.REQUESTED
        ).count()

    def resolve_scheduled_jobs(self, info):
        from jobs.models import Job
        from django.db.models import Q
        return Job.objects.filter(
            Q(customer=self) | Q(professional=self),
            status__in=[Job.Status.AGREED, Job.Status.IN_VISIT]
        ).count()

    def resolve_rejected_jobs(self, info):
        from jobs.models import Job
        from django.db.models import Q
        return Job.objects.filter(
            Q(customer=self) | Q(professional=self),
            status=Job.Status.CANCELLED
        ).count()

    def resolve_completed_jobs(self, info):
        from jobs.models import Job
        from django.db.models import Q
        return Job.objects.filter(
            Q(customer=self) | Q(professional=self),
            status=Job.Status.FINISHED
        ).count()

    def resolve_reviews_count(self, info):
        return 0

class SpecialtyType(DjangoObjectType):
    icon_url = graphene.String()

    class Meta:
        model = Specialty
        fields = ("id", "name", "icon", "icon_url", "color", "synonyms", "tags")

    def resolve_icon_url(self, info):
        if self.icon:
            return info.context.build_absolute_uri(self.icon.url)
        return None

class SubTagType(DjangoObjectType):
    class Meta:
        model = SubTag
        fields = ("id", "name", "color", "tag")

class TagType(DjangoObjectType):
    icon_url = graphene.String()
    subtags = graphene.List(lambda: SubTagType)

    class Meta:
        model = Tag
        fields = ("id", "name", "synonyms", "color", "icon", "icon_url", "specialty", "subtags")

    def resolve_icon_url(self, info):
        if self.icon:
            return info.context.build_absolute_uri(self.icon.url)
        return None

    def resolve_subtags(self, info):
        return self.subtags.all()


class CheckUserExistenceType(graphene.ObjectType):
    email_exists = graphene.Boolean()
    phone_exists = graphene.Boolean()

class ProfessionalPhotoType(DjangoObjectType):
    image_url = graphene.String()

    class Meta:
        model = ProfessionalPhoto
        fields = ("id", "image", "image_url", "uploaded_at")

    def resolve_image_url(self, info):
        if self.image:
            return info.context.build_absolute_uri(self.image.url)
        return None

class SubscriptionPlanType(DjangoObjectType):
    class Meta:
        model = SubscriptionPlan
        fields = (
            "id",
            "name",
            "description",
            "price",
            "duration_days",
            "monthly_requests",
            "urgent_requests",
            "service_categories",
            "search_position",
            "featured_badge",
            "rrss_campaigns",
            "radio_broadcast",
            "profile_statistics",
            "support_level",
            "is_coming_soon",
            "display_order",
        )


class ProfessionalDocumentType(DjangoObjectType):
    file_url = graphene.String()

    class Meta:
        model = ProfessionalDocument
        fields = ("id", "name", "is_visible", "status", "rejection_reason", "uploaded_at")

    def resolve_file_url(self, info):
        if self.file:
            return info.context.build_absolute_uri(self.file.url)
        return None

class ProfessionalProfileType(DjangoObjectType):
    documents = graphene.List(ProfessionalDocumentType)
    requires_plan_upgrade = graphene.Boolean()
    specialties = graphene.List(SpecialtyType)
    tags = graphene.List(TagType)

    class Meta:
        model = ProfessionalProfile
        fields = "__all__"

    def resolve_specialties(self, info):
        specs = list(self.specialties.all())
        if not specs and self.specialty:
            specs = [self.specialty]
        return specs

    def resolve_tags(self, info):
        tag_list = list(self.tags.all())
        if not tag_list and self.subtags.exists():
            from .models import Tag
            tag_ids = list(self.subtags.values_list('tag_id', flat=True).distinct())
            tag_list = list(Tag.objects.filter(id__in=tag_ids))
        return tag_list

    def resolve_documents(self, info):
        user = info.context.user
        if not user.is_anonymous and user == self.user:
            return self.documents.all()
        return self.documents.filter(is_visible=True)

    def resolve_requires_plan_upgrade(self, info):
        return self.requires_plan_upgrade

class Query(graphene.ObjectType):
    me = graphene.Field(UserType)
    specialties = graphene.List(SpecialtyType)
    tags = graphene.List(TagType)
    subtags = graphene.List(SubTagType)
    professionals = graphene.List(ProfessionalProfileType, specialty_id=graphene.Int())
    my_favorites = graphene.List(UserType)
    subscription_plans = graphene.List(SubscriptionPlanType)
    max_specialties_per_tradesman = graphene.Int()

    def resolve_max_specialties_per_tradesman(self, info):
        user = info.context.user
        if not user.is_anonymous and hasattr(user, 'professional_profile'):
            profile = user.professional_profile
            if profile and profile.plan:
                if profile.plan.service_categories is None:
                    return 9999  # Unlimited plan
                return profile.plan.service_categories
        
        # For new/anonymous users during registration: use Plan Inicial limit!
        from .models import SubscriptionPlan
        initial_plan = SubscriptionPlan.objects.filter(name='Plan Inicial').first()
        if initial_plan:
            if initial_plan.service_categories is None:
                return 9999
            return initial_plan.service_categories

        from .models import SystemSetting
        return SystemSetting.get_max_specialties()
    
    # Nueva query para verificar disponibilidad de correo o teléfono en tiempo real
    check_user_existence = graphene.Field(
        CheckUserExistenceType,
        email=graphene.String(),
        phone_number=graphene.String()
    )

    def resolve_check_user_existence(self, info, email=None, phone_number=None):
        email_exists = False
        phone_exists = False
        if email and email.strip():
            email_clean = email.strip().lower()
            email_exists = User.objects.filter(
                Q(email__iexact=email_clean) | Q(username__iexact=email_clean)
            ).exists()
        if phone_number and phone_number.strip():
            phone_clean = phone_number.strip()
            phone_exists = User.objects.filter(phone_number=phone_clean).exists()
        return CheckUserExistenceType(email_exists=email_exists, phone_exists=phone_exists)

    # Nueva query para buscar maestros cercanos (soporta filtro de texto)
    nearby_professionals = graphene.List(
        UserType,
        latitude=graphene.Float(required=True),
        longitude=graphene.Float(required=True),
        radius_km=graphene.Float(default_value=10000000.0),
        specialty_id=graphene.Int(),
        query=graphene.String(),
        tag_ids=graphene.List(graphene.Int),
        subtag_ids=graphene.List(graphene.Int)
    )

    def resolve_me(self, info):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')
        return user

    def resolve_specialties(self, info):
        return Specialty.objects.all()

    def resolve_tags(self, info):
        return Tag.objects.all()

    def resolve_subtags(self, info):
        return SubTag.objects.all()

    def resolve_my_favorites(self, info):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')
        return user.favorite_professionals.all()

    def resolve_subscription_plans(self, info):
        return SubscriptionPlan.objects.exclude(name__iexact='Plan Inicial').order_by('display_order', 'id')

    def resolve_professionals(self, info, specialty_id=None):
        queryset = ProfessionalProfile.objects.filter(is_verified=True)
        if specialty_id:
            queryset = queryset.filter(specialty_id=specialty_id)
        return queryset

    def resolve_nearby_professionals(self, info, latitude, longitude, radius_km, specialty_id=None, query=None, tag_ids=None, subtag_ids=None):
        from math import cos, radians, sin, atan2, sqrt
        from django.db.models import Q

        # Filtramos usuarios que sean profesionales, estén disponibles y tengan ubicación (profesional o de usuario)
        queryset = User.objects.filter(
            user_type=User.UserType.PROFESSIONAL,
            is_available=True
        ).filter(
            Q(professional_profile__latitude__isnull=False, professional_profile__longitude__isnull=False) |
            Q(latitude__isnull=False, longitude__isnull=False)
        )

        if specialty_id:
            queryset = queryset.filter(professional_profile__specialty_id=specialty_id)

        if tag_ids:
            queryset = queryset.filter(professional_profile__tags__id__in=tag_ids).distinct()

        if subtag_ids:
            from .models import SubTag
            parent_tag_ids = SubTag.objects.filter(id__in=subtag_ids).values_list('tag_id', flat=True)
            queryset = queryset.filter(
                Q(professional_profile__subtags__id__in=subtag_ids) |
                Q(professional_profile__tags__id__in=parent_tag_ids)
            ).distinct()

        if query:
            from .models import SubTag
            matching_subtags = SubTag.objects.filter(
                Q(name__icontains=query)
            )
            # Parent tags of matching subtags should also match
            parent_tags_of_subtags = Tag.objects.filter(subtags__in=matching_subtags)
            
            matching_tags = Tag.objects.filter(
                Q(name__icontains=query) | Q(synonyms__icontains=query)
            ) | parent_tags_of_subtags
            
            queryset = queryset.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(username__icontains=query) |
                Q(professional_profile__specialty__name__icontains=query) |
                Q(professional_profile__specialty__synonyms__icontains=query) |
                Q(professional_profile__bio__icontains=query) |
                Q(professional_profile__tags__in=matching_tags) |
                Q(professional_profile__subtags__in=matching_subtags)
            ).distinct()

        # Cálculo aproximado de Bounding Box (1 grado latitud ~ 111km)
        lat_range = radius_km / 111.0
        lon_range = radius_km / (111.0 * cos(radians(latitude)))

        filtered_queryset = queryset.filter(
            Q(professional_profile__latitude__range=(latitude - lat_range, latitude + lat_range),
              professional_profile__longitude__range=(longitude - lon_range, longitude + lon_range)) |
            Q(latitude__range=(latitude - lat_range, latitude + lat_range),
              longitude__range=(longitude - lon_range, longitude + lon_range))
        )

        # Convert to list and calculate Haversine distance for each
        results = list(filtered_queryset)

        def calculate_haversine(lat1, lon1, lat2, lon2):
            R = 6371.0  # Radius of earth in kilometers
            d_lat = radians(lat2 - lat1)
            d_lon = radians(lon2 - lon1)
            a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
            c = 2 * atan2(sqrt(a), sqrt(1 - a))
            return R * c

        for user in results:
            prof = getattr(user, 'professional_profile', None)
            prof_lat = prof.latitude if prof and prof.latitude is not None else user.latitude
            prof_lon = prof.longitude if prof and prof.longitude is not None else user.longitude

            if prof_lat is not None and prof_lon is not None:
                user.distance = calculate_haversine(
                    latitude,
                    longitude,
                    float(prof_lat),
                    float(prof_lon)
                )
            else:
                user.distance = 0.0

        def get_plan_priority(u):
            prof = getattr(u, 'professional_profile', None)
            if not prof or not prof.plan:
                return 0
            pos = prof.plan.search_position
            if pos == "Prioridad máxima":
                return 2
            elif pos == "Preferente":
                return 1
            return 0

        # Filtrar profesionales según su propio radio de movilidad/servicio (service_radius)
        in_radius_results = []
        for user in results:
            prof = getattr(user, 'professional_profile', None)
            max_radius = prof.service_radius if (prof and prof.service_radius is not None) else 10
            if user.distance <= max_radius:
                in_radius_results.append(user)
        results = in_radius_results

        # Sort by plan search priority (descending) then distance (ascending)
        results.sort(key=lambda u: (-get_plan_priority(u), u.distance))
        return results

import base64
from django.core.files.base import ContentFile

class UpdateProfile(graphene.Mutation):
    class Arguments:
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        email = graphene.String(required=True)
        phone_number = graphene.String()
        address = graphene.String()
        latitude = graphene.Float()
        longitude = graphene.Float()
        avatar_base64 = graphene.String()

    user = graphene.Field(UserType)
    success = graphene.Boolean()

    def mutate(self, info, first_name, last_name, email, phone_number=None, address=None, latitude=None, longitude=None, avatar_base64=None):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')

        if len(first_name) > 30:
            raise Exception('El nombre no puede tener más de 30 caracteres')
        if len(last_name) > 30:
            raise Exception('El apellido no puede tener más de 30 caracteres')

        user.first_name = first_name
        user.last_name = last_name
        user.email = email.strip().lower()
        user.username = email.strip().lower()
        user.phone_number = phone_number
        
        if address is not None:
            user.address = address
        if latitude is not None:
            user.latitude = Decimal(str(latitude))
        if longitude is not None:
            user.longitude = Decimal(str(longitude))
            
        if avatar_base64:
            # Separar el header (ej. data:image/jpeg;base64,) del contenido real
            if ';base64,' in avatar_base64:
                header, imgstr = avatar_base64.split(';base64,')
                ext = header.split('/')[-1]
            else:
                imgstr = avatar_base64
                ext = 'jpg'
            
            import time
            file_name = f"avatar_{user.id}_{int(time.time())}.{ext}"
            user.avatar.save(file_name, ContentFile(base64.b64decode(imgstr)), save=False)
            
        user.save()
        
        return UpdateProfile(user=user, success=True)

class RegisterUser(graphene.Mutation):
    class Arguments:
        email = graphene.String(required=True)
        password = graphene.String(required=True)
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        phone_number = graphene.String()
        user_type = graphene.String()

    user = graphene.Field(UserType)
    success = graphene.Boolean()

    def mutate(self, info, email, password, first_name, last_name, phone_number=None, user_type='CUSTOMER'):
        email_clean = email.strip().lower()
        if len(first_name) > 30:
            raise Exception('El nombre no puede tener más de 30 caracteres')
        if len(last_name) > 30:
            raise Exception('El apellido no puede tener más de 30 caracteres')

        if User.objects.filter(email__iexact=email_clean).exists() or User.objects.filter(username__iexact=email_clean).exists():
            raise Exception('El usuario ya existe')

        user = User(
            username=email_clean,
            email=email_clean,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            phone_number=phone_number.strip() if phone_number else None,
            user_type=user_type
        )
        user.set_password(password)
        user.save()

        if user_type == 'PROFESSIONAL':
            from users.models import ProfessionalProfile, SubscriptionPlan
            initial_plan = SubscriptionPlan.objects.filter(name='Plan Inicial').first()
            ProfessionalProfile.objects.get_or_create(user=user, defaults={'plan': initial_plan})

        return RegisterUser(user=user, success=True)

class UpdateAvailability(graphene.Mutation):
    class Arguments:
        is_available = graphene.Boolean(required=True)
        is_emergency = graphene.Boolean(required=False)

    user = graphene.Field(UserType)
    success = graphene.Boolean()

    def mutate(self, info, is_available, is_emergency=None):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')

        prof = getattr(user, 'professional_profile', None)
        if user.user_type == 'PROFESSIONAL' and (not prof or not prof.is_verified):
            user.is_available = False
            user.is_emergency = False
            user.save()
            raise Exception('Tu perfil está en proceso de validación. No puedes activar tu disponibilidad aún.')

        user.is_available = is_available
        if is_emergency is not None:
            user.is_emergency = is_emergency

        # Coordination logic
        if user.is_emergency:
            user.is_available = True
        if not user.is_available:
            user.is_emergency = False

        user.save()
        return UpdateAvailability(user=user, success=True)

class ToggleFavorite(graphene.Mutation):
    class Arguments:
        professional_id = graphene.ID(required=True)
    
    success = graphene.Boolean()
    is_favorite = graphene.Boolean()

    def mutate(self, info, professional_id):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')
        
        try:
            professional = User.objects.get(id=professional_id, user_type=User.UserType.PROFESSIONAL)
        except User.DoesNotExist:
            raise Exception('Profesional no encontrado')

        if user.favorite_professionals.filter(id=professional.id).exists():
            user.favorite_professionals.remove(professional)
            is_fav = False
        else:
            user.favorite_professionals.add(professional)
            is_fav = True
        
        return ToggleFavorite(success=True, is_favorite=is_fav)

class UpdateFcmToken(graphene.Mutation):
    class Arguments:
        fcm_token = graphene.String(required=True)

    user = graphene.Field(UserType)
    success = graphene.Boolean()

    def mutate(self, info, fcm_token):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')

        # 1. Update legacy token on User model
        user.fcm_token = fcm_token
        user.save()

        # 2. Register/Update in UserDevice
        UserDevice.objects.update_or_create(
            fcm_token=fcm_token,
            defaults={'user': user}
        )

        return UpdateFcmToken(user=user, success=True)

class DeleteFcmToken(graphene.Mutation):
    class Arguments:
        fcm_token = graphene.String(required=True)

    success = graphene.Boolean()

    def mutate(self, info, fcm_token):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')

        # 1. Delete matching UserDevice mapping
        UserDevice.objects.filter(fcm_token=fcm_token, user=user).delete()

        # 2. Clear legacy token if it matches
        if user.fcm_token == fcm_token:
            user.fcm_token = None
            user.save()

        return DeleteFcmToken(success=True)


class UpdateProfessionalProfile(graphene.Mutation):
    class Arguments:
        bio = graphene.String()
        hourly_rate = graphene.Float()
        service_radius = graphene.Int()
        facebook_url = graphene.String()
        instagram_url = graphene.String()
        tiktok_url = graphene.String()
        address = graphene.String()
        latitude = graphene.Float()
        longitude = graphene.Float()
        tag_ids = graphene.List(graphene.ID)
        subtag_ids = graphene.List(graphene.ID)
        specialty_id = graphene.Int()
        specialty_ids = graphene.List(graphene.ID)

    success = graphene.Boolean()
    user = graphene.Field(UserType)

    def mutate(self, info, bio=None, hourly_rate=None, service_radius=None, 
               facebook_url=None, instagram_url=None, tiktok_url=None, 
               address=None, latitude=None, longitude=None,
               tag_ids=None, subtag_ids=None, specialty_id=None, specialty_ids=None):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')
        
        if user.user_type != User.UserType.PROFESSIONAL:
            raise Exception('El usuario no es un profesional')
            
        profile, created = ProfessionalProfile.objects.get_or_create(user=user)
        
        if bio is not None:
            profile.bio = bio
        if hourly_rate is not None:
            profile.hourly_rate = Decimal(str(hourly_rate))
        if service_radius is not None:
            profile.service_radius = service_radius
        if facebook_url is not None:
            profile.facebook_url = facebook_url
        if instagram_url is not None:
            profile.instagram_url = instagram_url
        if tiktok_url is not None:
            profile.tiktok_url = tiktok_url
        if address is not None:
            profile.address = address
        if latitude is not None:
            profile.latitude = Decimal(str(latitude))
        if longitude is not None:
            profile.longitude = Decimal(str(longitude))

        if specialty_id is not None:
            profile.specialty_id = specialty_id

        if subtag_ids is not None:
            max_limit = SystemSetting.get_max_specialties()
            if profile.plan:
                if profile.plan.service_categories is None:
                    max_limit = None  # Unlimited plan
                else:
                    max_limit = profile.plan.service_categories

            if max_limit is not None and len(subtag_ids) > max_limit:
                raise Exception(f"Tu plan actual solo permite seleccionar hasta {max_limit} especializaciones.")
            profile.subtags.set(subtag_ids)

        if tag_ids is not None:
            max_tags = None
            if profile.plan:
                if profile.plan.service_categories is None:
                    max_tags = None  # Unlimited plan
                else:
                    max_tags = profile.plan.service_categories

            if max_tags is not None and len(tag_ids) > max_tags:
                raise Exception(f"Tu plan actual solo permite seleccionar hasta {max_tags} oficios/etiquetas.")
            profile.tags.set(tag_ids)

        if specialty_ids is not None:
            profile.specialties.set(specialty_ids)
            if specialty_ids:
                if not profile.specialty_id or profile.specialty_id not in [int(sid) for sid in specialty_ids if str(sid).isdigit()]:
                    try:
                        profile.specialty_id = int(specialty_ids[0])
                    except Exception:
                        pass
            else:
                profile.specialty_id = None

        if not profile.specialty_id and profile.specialties.exists():
            profile.specialty = profile.specialties.first()
            
        profile.save()
        return UpdateProfessionalProfile(success=True, user=user)

class AddPortfolioPhoto(graphene.Mutation):
    class Arguments:
        image_base64 = graphene.String(required=True)

    success = graphene.Boolean()
    photo = graphene.Field(ProfessionalPhotoType)
    user = graphene.Field(UserType)

    def mutate(self, info, image_base64):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')
            
        if user.user_type != User.UserType.PROFESSIONAL:
            raise Exception('El usuario no es un profesional')
            
        profile, created = ProfessionalProfile.objects.get_or_create(user=user)
        
        if profile.photos.count() >= 8:
            raise Exception('No puedes subir más de 8 fotos a tu portafolio')
            
        if ';base64,' in image_base64:
            header, imgstr = image_base64.split(';base64,')
            ext = header.split('/')[-1]
        else:
            imgstr = image_base64
            ext = 'jpg'
            
        import time
        file_name = f"portfolio_{user.id}_{int(time.time())}.{ext}"
        
        photo = ProfessionalPhoto(profile=profile)
        photo.image.save(file_name, ContentFile(base64.b64decode(imgstr)), save=True)
        
        return AddPortfolioPhoto(success=True, photo=photo, user=user)

class DeletePortfolioPhoto(graphene.Mutation):
    class Arguments:
        photo_id = graphene.ID(required=True)

    success = graphene.Boolean()
    user = graphene.Field(UserType)

    def mutate(self, info, photo_id):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')
            
        if user.user_type != User.UserType.PROFESSIONAL:
            raise Exception('El usuario no es un profesional')
            
        try:
            photo = ProfessionalPhoto.objects.get(id=photo_id, profile__user=user)
        except ProfessionalPhoto.DoesNotExist:
            raise Exception('Foto no encontrada o no pertenece a tu perfil')
            
        if photo.image:
            photo.image.delete(save=False)
        photo.delete()
        
        return DeletePortfolioPhoto(success=True, user=user)

class AddProfessionalDocument(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        file_base64 = graphene.String(required=True)

    success = graphene.Boolean()
    document = graphene.Field(ProfessionalDocumentType)
    user = graphene.Field(UserType)

    def mutate(self, info, name, file_base64):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')
            
        if user.user_type != User.UserType.PROFESSIONAL:
            raise Exception('El usuario no es un profesional')
            
        profile, created = ProfessionalProfile.objects.get_or_create(user=user)
        
        if ';base64,' in file_base64:
            header, file_str = file_base64.split(';base64,')
            ext = header.split('/')[-1]
            if 'pdf' in ext:
                ext = 'pdf'
            elif 'png' in ext:
                ext = 'png'
            elif 'jpeg' in ext or 'jpg' in ext:
                ext = 'jpg'
            else:
                ext = 'jpg'
        else:
            file_str = file_base64
            ext = 'jpg'
            
        import time
        file_name = f"doc_{user.id}_{int(time.time())}.{ext}"
        
        doc = ProfessionalDocument(profile=profile, name=name)
        doc.file.save(file_name, ContentFile(base64.b64decode(file_str)), save=True)
        
        return AddProfessionalDocument(success=True, document=doc, user=user)

class ToggleDocumentVisibility(graphene.Mutation):
    class Arguments:
        document_id = graphene.ID(required=True)
        is_visible = graphene.Boolean(required=True)

    success = graphene.Boolean()
    document = graphene.Field(ProfessionalDocumentType)
    user = graphene.Field(UserType)

    def mutate(self, info, document_id, is_visible):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')
            
        try:
            doc = ProfessionalDocument.objects.get(id=document_id, profile__user=user)
        except ProfessionalDocument.DoesNotExist:
            raise Exception('Documento no encontrado o no pertenece a tu perfil')
            
        doc.is_visible = is_visible
        doc.save()
        
        return ToggleDocumentVisibility(success=True, document=doc, user=user)

class DeleteProfessionalDocument(graphene.Mutation):
    class Arguments:
        document_id = graphene.ID(required=True)

    success = graphene.Boolean()
    user = graphene.Field(UserType)

    def mutate(self, info, document_id):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')
            
        try:
            doc = ProfessionalDocument.objects.get(id=document_id, profile__user=user)
        except ProfessionalDocument.DoesNotExist:
            raise Exception('Documento no encontrado o no pertenece a tu perfil')
            
        if doc.file:
            doc.file.delete(save=False)
        doc.delete()
        
        return DeleteProfessionalDocument(success=True, user=user)

import random
from django.utils import timezone
from datetime import timedelta

class RequestPasswordReset(graphene.Mutation):
    class Arguments:
        email = graphene.String(required=True)

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, email):
        generic_message = "Si el correo está registrado, recibirás un código en unos minutos."
        email_clean = email.strip().lower()
        try:
            user = User.objects.get(Q(email__iexact=email_clean) | Q(username__iexact=email_clean))
            
            # Generar OTP de 6 dígitos
            otp = f"{random.randint(100000, 999999)}"
            expires_at = timezone.now() + timedelta(minutes=15)
            
            # Guardar en base de datos
            PasswordResetOTP.objects.create(
                email=email_clean,
                otp_code=otp,
                expires_at=expires_at
            )

            # Enviar correo vía Resend (https://resend.com)
            from django.conf import settings
            import logging
            import traceback
            logger = logging.getLogger(__name__)

            subject = "Código de recuperación de contraseña - ClanShip"
            message_content = (
                f"Hola {user.first_name or user.username},\n\n"
                f"Has solicitado restablecer tu contraseña en ClanShip.\n"
                f"Tu código de verificación de 6 dígitos es:\n\n"
                f"      {otp}\n\n"
                f"Este código es válido por 15 minutos.\n"
                f"Si no solicitaste este cambio, por favor ignora este mensaje.\n\n"
                f"Atentamente,\n"
                f"El equipo de ClanShip"
            )

            try:
                import resend
                resend.api_key = settings.RESEND_API_KEY

                params: resend.Emails.SendParams = {
                    "from": settings.NO_REPLY_FROM_EMAIL,
                    "to": [user.email],
                    "subject": subject,
                    "text": message_content,
                }
                response = resend.Emails.send(params)
                logger.info(f"[RESEND] OTP enviado a '{user.email}'. id={response.get('id')}")

            except Exception as mail_err:
                err_type = type(mail_err).__name__
                err_msg  = str(mail_err)
                logger.error(
                    f"[EMAIL ERROR] No se pudo enviar OTP a '{email_clean}'.\n"
                    f"  Tipo de error : {err_type}\n"
                    f"  Mensaje       : {err_msg}\n"
                    f"  Traceback:\n{traceback.format_exc()}"
                )
                if 'api_key' in err_msg.lower() or 'unauthorized' in err_msg.lower():
                    logger.error(
                        "[EMAIL HINT] Verifica que RESEND_API_KEY esté configurado correctamente en .env"
                    )
                # Aún retornamos éxito para no revelar si el correo existe
            
            return RequestPasswordReset(success=True, message=generic_message)
        except User.DoesNotExist:
          return RequestPasswordReset(success=True, message=generic_message)


class VerifyPasswordResetOtp(graphene.Mutation):
    class Arguments:
        email = graphene.String(required=True)
        otp_code = graphene.String(required=True)

    success = graphene.Boolean()
    message = graphene.String()
    reset_token = graphene.String()

    def mutate(self, info, email, otp_code):
        email_clean = email.strip().lower()
        try:
            otp_record = PasswordResetOTP.objects.filter(
                email__iexact=email_clean,
                otp_code=otp_code,
                used=False,
                expires_at__gt=timezone.now()
            ).order_by('-created_at').first()

            if not otp_record:
                return VerifyPasswordResetOtp(success=False, message="Código inválido o expirado.")

            otp_record.verified = True
            otp_record.save()

            return VerifyPasswordResetOtp(
                success=True,
                message="Código verificado con éxito.",
                reset_token=str(otp_record.reset_token)
            )
        except Exception as e:
            return VerifyPasswordResetOtp(success=False, message=str(e))


class ResetPasswordWithOtp(graphene.Mutation):
    class Arguments:
        email = graphene.String(required=True)
        reset_token = graphene.String(required=True)
        new_password = graphene.String(required=True)

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, email, reset_token, new_password):
        email_clean = email.strip().lower()
        try:
            otp_record = PasswordResetOTP.objects.filter(
                email__iexact=email_clean,
                reset_token=reset_token,
                verified=True,
                used=False,
                expires_at__gt=timezone.now()
            ).first()

            if not otp_record:
                return ResetPasswordWithOtp(success=False, message="Token de recuperación inválido o expirado.")

            user = User.objects.get(Q(email__iexact=email_clean) | Q(username__iexact=email_clean))
            user.set_password(new_password)
            user.save()

            otp_record.used = True
            otp_record.save()

            return ResetPasswordWithOtp(success=True, message="Contraseña actualizada correctamente.")
        except User.DoesNotExist:
            return ResetPasswordWithOtp(success=False, message="Usuario no encontrado.")
        except Exception as e:
            return ResetPasswordWithOtp(success=False, message=str(e))


class SubscribeToPlan(graphene.Mutation):
    class Arguments:
        plan_id = graphene.ID(required=True)

    success = graphene.Boolean()
    profile = graphene.Field(ProfessionalProfileType)

    def mutate(self, info, plan_id):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')
        if user.user_type != User.UserType.PROFESSIONAL:
            raise Exception('El usuario debe ser un profesional')

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
                raise Exception(f'El plan {plan.name} solo permite {plan.service_categories} oficios, pero tienes {current_tags} seleccionados. Por favor, desmarca algunos antes de cambiar de plan.')

        profile.plan = plan
        from django.utils import timezone
        profile.plan_start_date = timezone.now()
        profile.save()

        return SubscribeToPlan(success=True, profile=profile)


class AddUserAddress(graphene.Mutation):
    class Arguments:
        address = graphene.String(required=True)
        latitude = graphene.Float(required=True)
        longitude = graphene.Float(required=True)
        alias = graphene.String(required=False)

    user_address = graphene.Field(UserAddressType)

    @login_required
    def mutate(self, info, address, latitude, longitude, alias=None):
        user = info.context.user
        if UserAddress.objects.filter(user=user).count() >= 3:
            raise Exception("No puedes guardar más de 3 direcciones.")
        
        user_address = UserAddress.objects.create(
            user=user,
            address=address,
            latitude=latitude,
            longitude=longitude,
            alias=alias
        )
        return AddUserAddress(user_address=user_address)


class DeleteUserAddress(graphene.Mutation):
    class Arguments:
        address_id = graphene.Int(required=True)

    success = graphene.Boolean()

    @login_required
    def mutate(self, info, address_id):
        user = info.context.user
        try:
            user_address = UserAddress.objects.get(pk=address_id, user=user)
            user_address.delete()
            return DeleteUserAddress(success=True)
        except UserAddress.DoesNotExist:
            raise Exception("Dirección no encontrada.")


class CustomObtainJSONWebToken(graphql_jwt.ObtainJSONWebToken):
    class Arguments:
        username = graphene.String(required=True)
        password = graphene.String(required=True)
        app_type = graphene.String(required=False, default_value="CLIENT")

    @classmethod
    def mutate(cls, root, info, **kwargs):
        if 'username' in kwargs and isinstance(kwargs['username'], str):
            kwargs['username'] = kwargs['username'].strip().lower()

        app_type = kwargs.get('app_type', 'CLIENT').upper()
        session_key = str(uuid.uuid4())

        if hasattr(info, 'context'):
            setattr(info.context, '_app_type', app_type)

        response = super().mutate(root, info, **kwargs)

        if response and getattr(response, 'token', None):
            try:
                username = kwargs.get(cls.username_field)
                user = User.objects.filter(Q(username__iexact=username) | Q(email__iexact=username)).first()
                if user:
                    if app_type == 'TRADESMAN':
                        user.tradesman_session_key = session_key
                        user.save(update_fields=['tradesman_session_key'])
                    else:
                        user.client_session_key = session_key
                        user.save(update_fields=['client_session_key'])

                    payload = graphql_jwt.utils.jwt_payload(user, info.context)
                    payload['app_type'] = app_type
                    payload['session_key'] = session_key
                    response.token = graphql_jwt.utils.jwt_encode(payload)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Error en CustomObtainJSONWebToken: {str(e)}")

        return response


class Mutation(graphene.ObjectType):
    token_auth = CustomObtainJSONWebToken.Field()
    verify_token = graphql_jwt.Verify.Field()
    refresh_token = graphql_jwt.Refresh.Field()
    update_profile = UpdateProfile.Field()
    register_user = RegisterUser.Field()
    toggle_favorite = ToggleFavorite.Field()
    update_availability = UpdateAvailability.Field()
    update_fcm_token = UpdateFcmToken.Field()
    delete_fcm_token = DeleteFcmToken.Field()
    update_professional_profile = UpdateProfessionalProfile.Field()
    add_portfolio_photo = AddPortfolioPhoto.Field()
    delete_portfolio_photo = DeletePortfolioPhoto.Field()
    add_professional_document = AddProfessionalDocument.Field()
    toggle_document_visibility = ToggleDocumentVisibility.Field()
    delete_professional_document = DeleteProfessionalDocument.Field()
    request_password_reset = RequestPasswordReset.Field()
    verify_password_reset_otp = VerifyPasswordResetOtp.Field()
    reset_password_with_otp = ResetPasswordWithOtp.Field()
    subscribe_to_plan = SubscribeToPlan.Field()
    add_user_address = AddUserAddress.Field()
    delete_user_address = DeleteUserAddress.Field()

