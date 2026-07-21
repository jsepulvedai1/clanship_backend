import graphene
from graphene_django import DjangoObjectType
from .models import Job
from django.contrib.auth import get_user_model
from graphql_jwt.decorators import login_required

User = get_user_model()

class JobType(DjangoObjectType):
    additional_photo_url = graphene.String()
    has_unread_messages = graphene.Boolean()
    cancelled_by_user_name = graphene.String()

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


class Mutation(graphene.ObjectType):
    create_job = CreateJob.Field()
    update_job_status = UpdateJobStatus.Field()
    mark_job_as_read = MarkJobAsRead.Field()
    enrich_job = EnrichJob.Field()
    schedule_job_visit = ScheduleJobVisit.Field()
