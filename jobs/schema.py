import graphene
from graphene_django import DjangoObjectType
from .models import Job
from django.contrib.auth import get_user_model
from graphql_jwt.decorators import login_required

User = get_user_model()

class JobType(DjangoObjectType):
    class Meta:
        model = Job
        fields = "__all__"

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

        job = Job.objects.create(
            customer=user,
            professional=professional,
            status=Job.Status.AGREED,
            **kwargs
        )

        return CreateJob(job=job)


class UpdateJobStatus(graphene.Mutation):
    """
    Mutación para actualizar el estado de un trabajo.
    """
    class Arguments:
        job_id = graphene.Int(required=True)
        new_status = graphene.String(required=True)

    job = graphene.Field(JobType)

    @login_required
    def mutate(self, info, job_id, new_status):
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
        job.save()

        return UpdateJobStatus(job=job)


class Query(graphene.ObjectType):
    job = graphene.Field(JobType, id=graphene.Int(required=True))
    my_jobs = graphene.List(JobType)

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
    def resolve_my_jobs(self, info):
        user = info.context.user
        from django.db.models import Q
        return Job.objects.filter(Q(customer=user) | Q(professional=user))

class Mutation(graphene.ObjectType):
    create_job = CreateJob.Field()
    update_job_status = UpdateJobStatus.Field()
