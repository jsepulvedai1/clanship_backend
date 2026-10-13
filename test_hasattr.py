import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()
from jobs.models import Job
from users.models import User

customer = User.objects.create_user(username='customer4_test')
prof = User.objects.create_user(username='prof4_test')
job = Job.objects.create(customer=customer, professional=prof, status=Job.Status.FINISHED)

try:
    has_rev = hasattr(job, 'review')
    print("hasattr returned:", has_rev)
except Exception as e:
    print("hasattr raised:", type(e))

job.delete()
customer.delete()
prof.delete()
