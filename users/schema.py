import graphene
from graphene_django import DjangoObjectType
from .models import User, Specialty, ProfessionalProfile, Tag, ProfessionalPhoto, ProfessionalDocument, SubscriptionPlan
import graphql_jwt
from decimal import Decimal
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail


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
            "is_favorite", "fcm_token"
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
        fields = ("id", "name", "icon", "icon_url", "color")

    def resolve_icon_url(self, info):
        if self.icon:
            return info.context.build_absolute_uri(self.icon.url)
        return None

class TagType(DjangoObjectType):
    class Meta:
        model = Tag
        fields = ("id", "name", "synonyms", "color")


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
        fields = ("id", "name", "description", "price", "duration_days")


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

    class Meta:
        model = ProfessionalProfile
        fields = "__all__"

    def resolve_documents(self, info):
        user = info.context.user
        if not user.is_anonymous and user == self.user:
            return self.documents.all()
        return self.documents.filter(is_visible=True)

class Query(graphene.ObjectType):
    me = graphene.Field(UserType)
    specialties = graphene.List(SpecialtyType)
    tags = graphene.List(TagType)
    professionals = graphene.List(ProfessionalProfileType, specialty_id=graphene.Int())
    my_favorites = graphene.List(UserType)
    subscription_plans = graphene.List(SubscriptionPlanType)
    
    # Nueva query para buscar maestros cercanos (soporta filtro de texto)
    nearby_professionals = graphene.List(
        UserType,
        latitude=graphene.Float(required=True),
        longitude=graphene.Float(required=True),
        radius_km=graphene.Float(default_value=10000000.0),
        specialty_id=graphene.Int(),
        query=graphene.String()
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

    def resolve_my_favorites(self, info):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')
        return user.favorite_professionals.all()

    def resolve_subscription_plans(self, info):
        return SubscriptionPlan.objects.all()

    def resolve_professionals(self, info, specialty_id=None):
        queryset = ProfessionalProfile.objects.filter(is_verified=True)
        if specialty_id:
            queryset = queryset.filter(specialty_id=specialty_id)
        return queryset

    def resolve_nearby_professionals(self, info, latitude, longitude, radius_km, specialty_id=None, query=None):
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

        if query:
            from django.db.models import Q
            matching_tags = Tag.objects.filter(
                Q(name__icontains=query) | Q(synonyms__icontains=query)
            )
            queryset = queryset.filter(
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(username__icontains=query) |
                Q(professional_profile__specialty__name__icontains=query) |
                Q(professional_profile__specialty__synonyms__icontains=query) |
                Q(professional_profile__bio__icontains=query) |
                Q(professional_profile__tags__in=matching_tags)
            ).distinct()

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

        if len(first_name) > 30:
            raise Exception('El nombre no puede tener más de 30 caracteres')
        if len(last_name) > 30:
            raise Exception('El apellido no puede tener más de 30 caracteres')

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
        if len(first_name) > 30:
            raise Exception('El nombre no puede tener más de 30 caracteres')
        if len(last_name) > 30:
            raise Exception('El apellido no puede tener más de 30 caracteres')

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

        if user_type == 'PROFESSIONAL':
            from users.models import ProfessionalProfile
            ProfessionalProfile.objects.get_or_create(user=user)

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

class UpdateFcmToken(graphene.Mutation):
    class Arguments:
        fcm_token = graphene.String(required=True)

    user = graphene.Field(UserType)
    success = graphene.Boolean()

    def mutate(self, info, fcm_token):
        user = info.context.user
        if user.is_anonymous:
            raise Exception('No autenticado')

        user.fcm_token = fcm_token
        user.save()
        return UpdateFcmToken(user=user, success=True)

class UpdateProfessionalProfile(graphene.Mutation):
    class Arguments:
        bio = graphene.String()
        hourly_rate = graphene.Float()
        service_radius = graphene.Int()
        facebook_url = graphene.String()
        instagram_url = graphene.String()
        tiktok_url = graphene.String()
        tag_ids = graphene.List(graphene.ID)
        specialty_id = graphene.Int()
        specialty_ids = graphene.List(graphene.ID)

    success = graphene.Boolean()
    user = graphene.Field(UserType)

    def mutate(self, info, bio=None, hourly_rate=None, service_radius=None, 
               facebook_url=None, instagram_url=None, tiktok_url=None, tag_ids=None,
               specialty_id=None, specialty_ids=None):
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
        if specialty_id is not None:
            profile.specialty_id = specialty_id
            
        if tag_ids is not None:
            # tag_ids can be a list of IDs or strings
            profile.tags.set(tag_ids)
            
        if specialty_ids is not None:
            profile.specialties.set(specialty_ids)
            
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

class RequestPasswordReset(graphene.Mutation):
    class Arguments:
        email = graphene.String(required=True)

    success = graphene.Boolean()
    message = graphene.String()

    def mutate(self, info, email):
        try:
            user = User.objects.get(email=email)
            
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            
            domain = info.context.get_host()
            protocol = 'https' if info.context.is_secure() else 'http'
            reset_url = f"{protocol}://{domain}/auth/reset/{uid}/{token}/"
            
            subject = "Recuperación de contraseña - ClanShip"
            message_content = (
                f"Hola {user.first_name},\n\n"
                f"Para restablecer tu contraseña en ClanShip, haz clic en el siguiente enlace:\n"
                f"{reset_url}\n\n"
                f"Este enlace es válido solo por tiempo limitado.\n"
                f"Si no solicitaste este cambio, por favor ignora este mensaje.\n\n"
                f"Atentamente,\n"
                f"El equipo de ClanShip"
            )
            
            send_mail(
                subject,
                message_content,
                None,
                [user.email],
                fail_silently=False,
            )
            
            return RequestPasswordReset(success=True, message="Se ha enviado un correo con las instrucciones.")
        except User.DoesNotExist:
            return RequestPasswordReset(success=True, message="Se ha enviado un correo con las instrucciones.")


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

        profile.plan = plan
        profile.save()

        return SubscribeToPlan(success=True, profile=profile)

class Mutation(graphene.ObjectType):
    token_auth = graphql_jwt.ObtainJSONWebToken.Field()
    verify_token = graphql_jwt.Verify.Field()
    refresh_token = graphql_jwt.Refresh.Field()
    update_profile = UpdateProfile.Field()
    register_user = RegisterUser.Field()
    toggle_favorite = ToggleFavorite.Field()
    update_availability = UpdateAvailability.Field()
    update_fcm_token = UpdateFcmToken.Field()
    update_professional_profile = UpdateProfessionalProfile.Field()
    add_portfolio_photo = AddPortfolioPhoto.Field()
    delete_portfolio_photo = DeletePortfolioPhoto.Field()
    add_professional_document = AddProfessionalDocument.Field()
    toggle_document_visibility = ToggleDocumentVisibility.Field()
    delete_professional_document = DeleteProfessionalDocument.Field()
    request_password_reset = RequestPasswordReset.Field()
    subscribe_to_plan = SubscribeToPlan.Field()

