import os, django, traceback
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from users.models import User
from jobs.models import Job, JobReview
from jobs.schema import RateJob
import graphene
from graphql.execution.base import ResolveInfo

customer = User.objects.create_user(username='customer3_test', password='123', user_type='CUSTOMER')
prof = User.objects.create_user(username='prof3_test', password='123', user_type='TRADESMAN')
job = Job.objects.create(customer=customer, professional=prof, status=Job.Status.FINISHED)

class DummyContext:
    def __init__(self, user):
        self.user = user

class DummyInfo(ResolveInfo):
    def __init__(self, context):
        self.context = context

info = DummyInfo(DummyContext(customer))

try:
    mutation = RateJob()
    result = mutation.mutate(info, job_id=job.id, rating=5, comment='Great')
    print("Success:", getattr(result, 'success', None))
    print("Review created:", JobReview.objects.filter(job=job).exists())
except Exception as e:
    traceback.print_exc()

job.delete()
customer.delete()
prof.delete()
