import graphene
from graphene_django import DjangoObjectType
from .models import Job, JobReview, PublicJobRequest, JobProposal
from users.models import Specialty
from django.contrib.auth import get_user_model
from graphql_jwt.decorators import login_required
import datetime
from django.utils import timezone
import math

def haversine_km(lat1, lon1, lat2, lon2):
    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2.0)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0)**2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return R * c
    except (ValueError, TypeError):
        return 0.0


class JobProposalType(DjangoObjectType):
    professional_name = graphene.String()
    professional_avatar_url = graphene.String()
    professional_rating = graphene.Float()

    class Meta:
        model = JobProposal
        fields = "__all__"

    def resolve_professional_name(self, info):
        return self.professional.get_full_name() or self.professional.username

    def resolve_professional_avatar_url(self, info):
        prof_profile = getattr(self.professional, 'professional_profile', None)
        if prof_profile and prof_profile.profile_photo:
            return info.context.build_absolute_uri(prof_profile.profile_photo.url)
        return None

    def resolve_professional_rating(self, info):
        prof_profile = getattr(self.professional, 'professional_profile', None)
        return prof_profile.rating if prof_profile else 0.0


class PublicJobRequestType(DjangoObjectType):
    photo_url = graphene.String()
    proposals_count = graphene.Int()
    proposals = graphene.List(JobProposalType)
    customer_name = graphene.String()
    specialty_name = graphene.String()
    has_submitted_proposal = graphene.Boolean()
    my_proposal = graphene.Field(JobProposalType)

    class Meta:
        model = PublicJobRequest
        fields = "__all__"

    def resolve_photo_url(self, info):
        if self.photo:
            return info.context.build_absolute_uri(self.photo.url)
        return None

    def resolve_proposals_count(self, info):
        return self.proposals.count()

    def resolve_proposals(self, info):
        return self.proposals.all().order_by('-created_at')

    def resolve_customer_name(self, info):
        return self.customer.get_full_name() or self.customer.username

    def resolve_specialty_name(self, info):
        if self.custom_specialty:
            return self.custom_specialty
        return self.specialty.name if self.specialty else ""

    def resolve_has_submitted_proposal(self, info):
        user = info.context.user
        if user.is_anonymous:
            return False
        return self.proposals.filter(professional=user).exists()

    def resolve_my_proposal(self, info):
        user = info.context.user
        if user.is_anonymous:
            return None
        return self.proposals.filter(professional=user).first()

User = get_user_model()

class JobReviewType(DjangoObjectType):
    customer_name = graphene.String()

    class Meta:
        model = JobReview
        fields = "__all__"

    def resolve_customer_name(self, info):
        return self.customer.get_full_name() or self.customer.username


class JobType(DjangoObjectType):
    additional_photo_url = graphene.String()
    has_unread_messages = graphene.Boolean()
    cancelled_by_user_name = graphene.String()
    has_been_reviewed = graphene.Boolean()
    review = graphene.Field(JobReviewType)

    class Meta:
        model = Job
        fields = "__all__"

    def resolve_additional_photo_url(self, info):
        if self.additional_photo:
            return info.context.build_absolute_uri(self.additional_photo.url)
        return None

    def resolve_has_unread_messages(self, info):
        user = info.context.user
        try:
            chat_room = self.chat_room
            if chat_room:
                return chat_room.messages.exclude(sender=user).filter(is_read=False).exists()
        except Exception:
            pass
        return False

    def resolve_cancelled_by_user_name(self, info):
        if self.cancelled_by:
            return self.cancelled_by.get_full_name() or self.cancelled_by.username
        return None

    def resolve_has_been_reviewed(self, info):
        try:
            return hasattr(self, 'review') and self.review is not None
        except Exception:
            return False

    def resolve_review(self, info):
        try:
            return getattr(self, 'review', None)
        except Exception:
            return None

class CreateJob(graphene.Mutation):
    """
    Mutación para crear un nuevo trabajo (Job).
    El cliente se asigna automáticamente al usuario autenticado.
    """
    class Arguments:
        professional_id = graphene.Int(required=True)
        scheduled_date = graphene.Date(required=True)
        scheduled_time = graphene.Time(required=True)
        description = graphene.String(required=True)
        agreed_price = graphene.Decimal(required=True)
        address = graphene.String(required=True)

    job = graphene.Field(JobType)

    @login_required
    def mutate(self, info, professional_id, **kwargs):
        user = info.context.user
        
        # Verificar que el usuario no sea el mismo profesional
        if user.id == professional_id:
            raise Exception("No puedes contratarte a ti mismo.")

        # Validar que el profesional existe y tiene el rol adecuado
        try:
            professional = User.objects.get(pk=professional_id, user_type='PROFESSIONAL')
        except User.DoesNotExist:
            raise Exception("El profesional no existe o no tiene un perfil válido.")
        # Validar que la ubicación del cliente esté dentro del radio de cobertura del profesional
        prof_profile = getattr(professional, 'professional_profile', None)
        if prof_profile:
            max_radius = prof_profile.service_radius or 10
            cust_lat = user.latitude
            cust_lon = user.longitude
            prof_lat = prof_profile.latitude or professional.latitude
            prof_lon = prof_profile.longitude or professional.longitude

            if cust_lat is not None and cust_lon is not None and prof_lat is not None and prof_lon is not None:
                from math import cos, radians, sin, atan2, sqrt
                def calc_dist(lat1, lon1, lat2, lon2):
                    R = 6371.0
                    d_lat = radians(lat2 - lat1)
                    d_lon = radians(lon2 - lon1)
                    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
                    return R * (2 * atan2(sqrt(a), sqrt(1 - a)))

                dist = calc_dist(float(cust_lat), float(cust_lon), float(prof_lat), float(prof_lon))
                if dist > max_radius:
                    raise Exception(f"El profesional sólo ofrece servicio dentro de su radio de cobertura ({max_radius} km).")

        # Check if an active job already exists between this customer and professional
        active_job = Job.objects.filter(
            customer=user,
            professional=professional,
            status__in=[Job.Status.REQUESTED, Job.Status.AGREED, Job.Status.IN_VISIT]
        ).first()

        if active_job:
            from chat.models import ChatRoom
            room, created = ChatRoom.objects.get_or_create(
                customer=user,
                professional=professional,
            )
            room.job = active_job
            room.save()
            return CreateJob(job=active_job)

        job = Job.objects.create(
            customer=user,
            professional=professional,
            status=Job.Status.REQUESTED,
            **kwargs
        )

        from chat.models import ChatRoom
        room, created = ChatRoom.objects.get_or_create(
            customer=user,
            professional=professional,
        )
        room.job = job
        room.save()

        return CreateJob(job=job)


class UpdateJobStatus(graphene.Mutation):
    """
    Mutación para actualizar el estado de un trabajo.
    """
    class Arguments:
        job_id = graphene.Int(required=True)
        new_status = graphene.String(required=True)
        cancellation_reason = graphene.String(required=False)

    job = graphene.Field(JobType)

    @login_required
    def mutate(self, info, job_id, new_status, cancellation_reason=None):
        user = info.context.user
        try:
            job = Job.objects.get(pk=job_id)
        except Job.DoesNotExist:
            raise Exception("El trabajo no existe.")

        # Permisos: Solo cliente o profesional pueden cambiar el estado
        if job.customer != user and job.professional != user:
            raise Exception("No tienes permiso para modificar este trabajo.")

        # Validar estado
        if new_status not in Job.Status.values:
            raise Exception(f"Estado '{new_status}' no es válido.")

        job.status = new_status
        if cancellation_reason or new_status == Job.Status.CANCELLED:
            job.cancellation_reason = cancellation_reason
            job.cancelled_by = user

        job.save()

        return UpdateJobStatus(job=job)


class MarkJobAsRead(graphene.Mutation):
    """
    Mutación para marcar un trabajo como leído por el profesional.
    """
    class Arguments:
        job_id = graphene.Int(required=True)

    success = graphene.Boolean()
    job = graphene.Field(JobType)

    @login_required
    def mutate(self, info, job_id):
        user = info.context.user
        try:
            job = Job.objects.get(pk=job_id)
        except Job.DoesNotExist:
            raise Exception("El trabajo no existe.")

        # Solo el profesional asignado puede marcarlo como leído
        if job.professional != user:
            raise Exception("No tienes permiso para modificar este trabajo.")

        job.is_read = True
        job.save()

        return MarkJobAsRead(success=True, job=job)


class Query(graphene.ObjectType):
    job = graphene.Field(JobType, id=graphene.Int(required=True))
    my_jobs = graphene.List(JobType, status=graphene.String())
    open_public_job_requests = graphene.List(PublicJobRequestType, specialty_id=graphene.Int(required=False))
    my_public_job_requests = graphene.List(PublicJobRequestType)
    public_job_request_details = graphene.Field(PublicJobRequestType, id=graphene.Int(required=True))

    @login_required
    def resolve_job(self, info, id):
        user = info.context.user
        try:
            job = Job.objects.get(pk=id)
            if job.customer == user or job.professional == user:
                return job
            raise Exception("No tienes permiso para ver este trabajo.")
        except Job.DoesNotExist:
            return None

    @login_required
    def resolve_my_jobs(self, info, status=None):
        user = info.context.user
        from django.db.models import Q
        queryset = Job.objects.filter(Q(customer=user) | Q(professional=user))
        if status:
            queryset = queryset.filter(status=status)
        return queryset

    @login_required
    def resolve_open_public_job_requests(self, info, specialty_id=None):
        user = info.context.user
        queryset = PublicJobRequest.objects.filter(status=PublicJobRequest.Status.OPEN)

        # Si es un profesional, filtrar por sus especialidades y radio de trabajo (service_radius)
        prof_profile = getattr(user, 'professional_profile', None)
        if prof_profile:
            if specialty_id:
                queryset = queryset.filter(specialty_id=specialty_id)
            else:
                from django.db.models import Q
                prof_specialty_ids = set()
                if prof_profile.specialty_id:
                    prof_specialty_ids.add(prof_profile.specialty_id)
                if hasattr(prof_profile, 'specialties'):
                    prof_specialty_ids.update(prof_profile.specialties.values_list('id', flat=True))

                if prof_specialty_ids:
                    queryset = queryset.filter(
                        Q(specialty_id__in=prof_specialty_ids) | Q(specialty__isnull=True) | Q(custom_specialty__isnull=False)
                    )

            if prof_profile.latitude and prof_profile.longitude:
                max_radius = float(prof_profile.service_radius or 30.0)
                filtered_ids = []
                for req in queryset:
                    if req.latitude and req.longitude:
                        dist = haversine_km(prof_profile.latitude, prof_profile.longitude, req.latitude, req.longitude)
                        if dist <= max_radius:
                            filtered_ids.append(req.id)
                    else:
                        # Si la solicitud no tiene coordenadas explícitas, incluirla
                        filtered_ids.append(req.id)
                queryset = queryset.filter(id__in=filtered_ids)

        return queryset.order_by('-created_at')

    @login_required
    def resolve_my_public_job_requests(self, info):
        user = info.context.user
        return PublicJobRequest.objects.filter(customer=user).order_by('-created_at')

    @login_required
    def resolve_public_job_request_details(self, info, id):
        try:
            return PublicJobRequest.objects.get(pk=id)
        except PublicJobRequest.DoesNotExist:
            return None

import base64
from django.core.files.base import ContentFile

class EnrichJob(graphene.Mutation):
    """
    Mutación para que el cliente enriquezca la solicitud de trabajo con detalles y fotos.
    """
    class Arguments:
        job_id = graphene.Int(required=True)
        enriched_details = graphene.String(required=True)
        photo_base64 = graphene.String(required=False)

    success = graphene.Boolean()
    job = graphene.Field(JobType)

    @login_required
    def mutate(self, info, job_id, enriched_details, photo_base64=None):
        user = info.context.user
        try:
            job = Job.objects.get(pk=job_id)
        except Job.DoesNotExist:
            raise Exception("El trabajo no existe.")

        if job.customer != user:
            raise Exception("No tienes permiso para modificar este trabajo.")

        job.enriched_details = enriched_details

        if photo_base64:
            try:
                format, imgstr = photo_base64.split(';base64,') 
                ext = format.split('/')[-1] 
            except ValueError:
                imgstr = photo_base64
                ext = "png"
            
            data = ContentFile(base64.b64decode(imgstr), name=f"job_{job_id}_additional.{ext}")
            job.additional_photo = data

        job.save()
        return EnrichJob(success=True, job=job)


class ScheduleJobVisit(graphene.Mutation):
    """
    Mutación para que el profesional agende/programe la visita y el aviso push.
    """
    class Arguments:
        job_id = graphene.Int(required=True)
        scheduled_date = graphene.Date(required=True)
        scheduled_time = graphene.Time(required=True)
        notification_lead_minutes = graphene.Int(required=True)
        agreed_price = graphene.Decimal(required=False)

    success = graphene.Boolean()
    job = graphene.Field(JobType)

    @login_required
    def mutate(self, info, job_id, scheduled_date, scheduled_time, notification_lead_minutes, agreed_price=None):
        user = info.context.user
        try:
            job = Job.objects.get(pk=job_id)
        except Job.DoesNotExist:
            raise Exception("El trabajo no existe.")

        if job.professional != user:
            raise Exception("No tienes permiso para programar esta visita.")

        job.scheduled_date = scheduled_date
        job.scheduled_time = scheduled_time
        job.notification_lead_minutes = notification_lead_minutes
        if agreed_price is not None:
            job.agreed_price = agreed_price
        job.status = Job.Status.SCHEDULED
        job.lead_notification_sent = False  # Reset reminder flag
        job.save()

        # Notificar al cliente de la programación de la visita
        try:
            cust = job.customer
            if cust:
                prof_name = job.professional.get_full_name() or job.professional.username
                from core.firebase import send_user_push_notification
                send_user_push_notification(
                    user=cust,
                    title="Propuesta de Visita Programada",
                    body=f"El profesional {prof_name} ha propuesto una visita para el {scheduled_date} a las {scheduled_time}. Por favor valida la agenda.",
                    data={"event": "job_updated", "job_id": job.id}
                )
        except Exception as e:
            print(f"Error al enviar notificacion push: {e}")

        return ScheduleJobVisit(success=True, job=job)


class RateJob(graphene.Mutation):
    """
    Mutación para que el cliente califique y comente sobre un trabajo finalizado.
    """
    class Arguments:
        job_id = graphene.Int(required=True)
        rating = graphene.Int(required=True)
        comment = graphene.String(required=False)

    success = graphene.Boolean()
    job = graphene.Field(JobType)
    review = graphene.Field(JobReviewType)

    @login_required
    def mutate(self, info, job_id, rating, comment=None):
        user = info.context.user
        try:
            job = Job.objects.get(pk=job_id)
        except Job.DoesNotExist:
            raise Exception("El trabajo no existe.")

        if job.customer != user:
            raise Exception("Sólo el cliente que solicitó el trabajo puede calificarlo.")

        if job.status != Job.Status.FINISHED:
            raise Exception("Sólo se pueden calificar trabajos que hayan sido finalizados.")

        try:
            if hasattr(job, 'review') and job.review is not None:
                raise Exception("Este trabajo ya ha sido calificado anteriormente.")
        except JobReview.DoesNotExist:
            pass

        if rating < 1 or rating > 5:
            raise Exception("La calificación debe ser un valor entre 1 y 5 estrellas.")

        review = JobReview.objects.create(
            job=job,
            customer=user,
            professional=job.professional,
            rating=rating,
            comment=comment
        )

        return RateJob(success=True, job=job, review=review)


# --- NUEVAS MUTACIONES Y TIPOS PARA SOLICITUDES ABIERTAS (MARKETPLACE) ---

class CreatePublicJobRequest(graphene.Mutation):
    class Arguments:
        specialty_id = graphene.Int(required=False)
        custom_specialty = graphene.String(required=False)
        title = graphene.String(required=True)
        description = graphene.String(required=True)
        address = graphene.String(required=True)
        latitude = graphene.Decimal(required=False)
        longitude = graphene.Decimal(required=False)
        budget = graphene.Decimal(required=False)
        is_urgent = graphene.Boolean(required=False)

    success = graphene.Boolean()
    public_request = graphene.Field(PublicJobRequestType)

    @login_required
    def mutate(self, info, title, description, address, specialty_id=None, custom_specialty=None, latitude=None, longitude=None, budget=None, is_urgent=False):
        user = info.context.user
        specialty = None
        if specialty_id:
            try:
                specialty = Specialty.objects.get(pk=specialty_id)
            except Specialty.DoesNotExist:
                pass

        if not specialty and custom_specialty:
            specialty, _ = Specialty.objects.get_or_create(name=custom_specialty.strip())

        expires_at = timezone.now() + datetime.timedelta(hours=48)

        public_request = PublicJobRequest.objects.create(
            customer=user,
            specialty=specialty,
            custom_specialty=custom_specialty.strip() if custom_specialty else None,
            title=title,
            description=description,
            address=address,
            latitude=latitude,
            longitude=longitude,
            budget=budget,
            is_urgent=is_urgent,
            expires_at=expires_at,
            status=PublicJobRequest.Status.OPEN
        )

        return CreatePublicJobRequest(success=True, public_request=public_request)


class SubmitJobProposal(graphene.Mutation):
    class Arguments:
        public_request_id = graphene.Int(required=True)
        estimated_price = graphene.Decimal(required=True)
        scheduled_date = graphene.Date(required=True)
        scheduled_time = graphene.Time(required=True)
        message = graphene.String(required=False)

    success = graphene.Boolean()
    proposal = graphene.Field(JobProposalType)

    @login_required
    def mutate(self, info, public_request_id, estimated_price, scheduled_date, scheduled_time, message=""):
        user = info.context.user
        if user.user_type != 'PROFESSIONAL':
            raise Exception("Solo los profesionales pueden enviar propuestas.")

        try:
            public_request = PublicJobRequest.objects.get(pk=public_request_id, status=PublicJobRequest.Status.OPEN)
        except PublicJobRequest.DoesNotExist:
            raise Exception("La solicitud abierta no existe o ya no se encuentra activa.")

        # Verificar límite de 5 propuestas por solicitud
        if public_request.proposals.count() >= 5:
            raise Exception("Esta solicitud ya ha alcanzado el límite máximo de 5 cotizaciones.")

        # Crear o actualizar propuesta del profesional
        proposal, created = JobProposal.objects.update_or_create(
            public_request=public_request,
            professional=user,
            defaults={
                'estimated_price': estimated_price,
                'scheduled_date': scheduled_date,
                'scheduled_time': scheduled_time,
                'message': message or "",
                'status': JobProposal.Status.PENDING
            }
        )

        # Notificar al cliente por push
        try:
            cust = public_request.customer
            if cust:
                prof_name = user.get_full_name() or user.username
                from core.firebase import send_user_push_notification
                send_user_push_notification(
                    user=cust,
                    title="Nueva Cotización Recibida",
                    body=f"El profesional {prof_name} ha enviado una propuesta de ${estimated_price} para '{public_request.title}'.",
                    data={"event": "job_proposal_received", "public_request_id": public_request.id}
                )
        except Exception:
            pass

        return SubmitJobProposal(success=True, proposal=proposal)


class AcceptJobProposal(graphene.Mutation):
    class Arguments:
        proposal_id = graphene.Int(required=True)

    success = graphene.Boolean()
    job = graphene.Field(JobType)

    @login_required
    def mutate(self, info, proposal_id):
        user = info.context.user
        try:
            proposal = JobProposal.objects.select_related('public_request', 'professional').get(pk=proposal_id)
        except JobProposal.DoesNotExist:
            raise Exception("La propuesta no existe.")

        public_request = proposal.public_request
        if public_request.customer != user:
            raise Exception("Solo el cliente dueño de la solicitud puede aceptar la cotización.")

        if public_request.status != PublicJobRequest.Status.OPEN:
            raise Exception("Esta solicitud ya fue asignada o no se encuentra activa.")

        # Marcar propuesta como aceptada y las demás como rechazadas
        proposal.status = JobProposal.Status.ACCEPTED
        proposal.save()
        public_request.proposals.exclude(pk=proposal.id).update(status=JobProposal.Status.REJECTED)
        public_request.status = PublicJobRequest.Status.ASSIGNED
        public_request.save()

        # Crear la instancia Job oficial
        job = Job.objects.create(
            customer=user,
            professional=proposal.professional,
            status=Job.Status.AGREED,
            agreed_price=proposal.estimated_price,
            scheduled_date=proposal.scheduled_date,
            scheduled_time=proposal.scheduled_time,
            address=public_request.address,
            description=f"SOLICITUD: {public_request.title}\n\n{public_request.description}"
        )

        # Crear o actualizar la sala de chat
        from chat.models import ChatRoom
        room, _ = ChatRoom.objects.get_or_create(
            customer=user,
            professional=proposal.professional
        )
        room.job = job
        room.save()

        # Enviar mensaje automático en la sala de chat con la propuesta aceptada
        from chat.models import Message
        Message.objects.create(
            room=room,
            sender=user,
            text=f"¡Hola! He aceptado tu cotización de ${proposal.estimated_price} para la visita del {proposal.scheduled_date} a las {proposal.scheduled_time}."
        )

        return AcceptJobProposal(success=True, job=job)


class CancelPublicJobRequest(graphene.Mutation):
    class Arguments:
        public_request_id = graphene.Int(required=True)

    success = graphene.Boolean()

    @login_required
    def mutate(self, info, public_request_id):
        user = info.context.user
        try:
            public_request = PublicJobRequest.objects.get(pk=public_request_id, customer=user)
        except PublicJobRequest.DoesNotExist:
            raise Exception("Solicitud no encontrada.")

        public_request.status = PublicJobRequest.Status.CANCELLED
        public_request.save()

        return CancelPublicJobRequest(success=True)


class Mutation(graphene.ObjectType):
    create_job = CreateJob.Field()
    update_job_status = UpdateJobStatus.Field()
    mark_job_as_read = MarkJobAsRead.Field()
    enrich_job = EnrichJob.Field()
    schedule_job_visit = ScheduleJobVisit.Field()
    rate_job = RateJob.Field()
    create_public_job_request = CreatePublicJobRequest.Field()
    submit_job_proposal = SubmitJobProposal.Field()
    accept_job_proposal = AcceptJobProposal.Field()
    cancel_public_job_request = CancelPublicJobRequest.Field()


