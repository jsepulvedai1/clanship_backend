import graphene
from graphene_django import DjangoObjectType
from .models import User, Specialty, ProfessionalProfile
import graphql_jwt
from decimal import Decimal

class UserType(DjangoObjectType):
    avatar_url = graphene.String()
    active_jobs = graphene.Int()
    completed_jobs = graphene.Int()
    scheduled_jobs = graphene.Int()
    rejected_jobs = graphene.Int()
    reviews_count = graphene.Int()
    is_favorite = graphene.Boolean()

    class Meta:
        model = User
        fields = (
            "id", "username", "email", "phone_number", "user_type", 
            "avatar", "latitude", "longitude", "address", 
            "is_available", "professional_profile", "first_name", "last_name",
            "active_jobs", "completed_jobs", "scheduled_jobs", "rejected_jobs", "reviews_count",
            "is_favorite"
        )

    def resolve_is_favorite(self, info):
        user = info.context.user
        if user.is_anonymous:
            return False
        return user.favorite_professionals.filter(id=self.id).exists()

    def resolve_avatar_url(self, info):
        if self.avatar:
            return info.context.build_absolute_uri(self.avatar.url)
        return None

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
    class Meta:
        model = Specialty
        fields = ("id", "name", "icon")

class ProfessionalProfileType(DjangoObjectType):
    class Meta:
        model = ProfessionalProfile
        fields = "__all__"

class Query(graphene.ObjectType):
    me = graphene.Field(UserType)
    specialties = graphene.List(SpecialtyType)
    professionals = graphene.List(ProfessionalProfileType, specialty_id=graphene.Int())
    my_favorites = graphene.List(UserType)
    
    # Nueva query para buscar maestros cercanos
    nearby_professionals = graphene.List(
        UserType,
        latitude=graphene.Float(required=True),
        longitude=graphene.Float(required=True),
        radius_km=graphene.Float(default_value=10000000.0),
        specialty_id=graphene.Int()
    )

    def resolve_me(self, info):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')
        return user

    def resolve_specialties(self, info):
        return Specialty.objects.all()

    def resolve_my_favorites(self, info):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')
        return user.favorite_professionals.all()

    def resolve_professionals(self, info, specialty_id=None):
        queryset = ProfessionalProfile.objects.filter(is_verified=True)
        if specialty_id:
            queryset = queryset.filter(specialty_id=specialty_id)
        return queryset

    def resolve_nearby_professionals(self, info, latitude, longitude, radius_km, specialty_id=None):
        from math import cos, radians
        
        # Filtramos usuarios que sean profesionales, estén disponibles y tengan ubicación
        queryset = User.objects.filter(
            user_type=User.UserType.PROFESSIONAL,
            is_available=True,
            latitude__isnull=False,
            longitude__isnull=False
        )

        if specialty_id:
            queryset = queryset.filter(professional_profile__specialty_id=specialty_id)

        # Cálculo aproximado de Bounding Box (1 grado latitud ~ 111km)
        lat_range = radius_km / 111.0
        lon_range = radius_km / (111.0 * cos(radians(latitude)))

        return queryset.filter(
            latitude__range=(latitude - lat_range, latitude + lat_range),
            longitude__range=(longitude - lon_range, longitude + lon_range)
        )

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

        user.first_name = first_name
        user.last_name = last_name
        user.email = email
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
        if User.objects.filter(email=email).exists() or User.objects.filter(username=email).exists():
            raise Exception('El usuario ya existe')

        user = User(
            username=email,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            user_type=user_type
        )
        user.set_password(password)
        user.save()
        return RegisterUser(user=user, success=True)

class UpdateAvailability(graphene.Mutation):
    class Arguments:
        is_available = graphene.Boolean(required=True)

    user = graphene.Field(UserType)
    success = graphene.Boolean()

    def mutate(self, info, is_available):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')

        user.is_available = is_available
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

class Mutation(graphene.ObjectType):
    token_auth = graphql_jwt.ObtainJSONWebToken.Field()
    verify_token = graphql_jwt.Verify.Field()
    refresh_token = graphql_jwt.Refresh.Field()
    update_profile = UpdateProfile.Field()
    register_user = RegisterUser.Field()
    toggle_favorite = ToggleFavorite.Field()
    update_availability = UpdateAvailability.Field()
