import graphene
from graphene_django import DjangoObjectType
from .models import User, Specialty, ProfessionalProfile
import graphql_jwt

class UserType(DjangoObjectType):
    avatar_url = graphene.String()

    class Meta:
        model = User
        fields = (
            "id", "username", "email", "phone_number", "user_type", 
            "avatar", "latitude", "longitude", "address", 
            "is_available", "professional_profile", "first_name", "last_name"
        )

    def resolve_avatar_url(self, info):
        if self.avatar:
            return info.context.build_absolute_uri(self.avatar.url)
        return None

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
    
    # Nueva query para buscar maestros cercanos
    nearby_professionals = graphene.List(
        UserType,
        latitude=graphene.Float(required=True),
        longitude=graphene.Float(required=True),
        radius_km=graphene.Float(default_value=10.0),
        specialty_id=graphene.Int()
    )

    def resolve_me(self, info):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')
        return user

    def resolve_specialties(self, info):
        return Specialty.objects.all()

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

class UpdateProfile(graphene.Mutation):
    class Arguments:
        first_name = graphene.String(required=True)
        last_name = graphene.String(required=True)
        email = graphene.String(required=True)
        phone_number = graphene.String()

    user = graphene.Field(UserType)
    success = graphene.Boolean()

    def mutate(self, info, first_name, last_name, email, phone_number=None):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')

        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.phone_number = phone_number
        user.save()
        
        return UpdateProfile(user=user, success=True)

class Mutation(graphene.ObjectType):
    token_auth = graphql_jwt.ObtainJSONWebToken.Field()
    verify_token = graphql_jwt.Verify.Field()
    refresh_token = graphql_jwt.Refresh.Field()
    update_profile = UpdateProfile.Field()
