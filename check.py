import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model
from jobs.models import Job, JobReview

User = get_user_model()
customer = User.objects.create(username="test_customer")
prof = User.objects.create(username="test_prof")

job = Job.objects.create(customer=customer, professional=prof, status='FINISHED', description="Test", agreed_price=1000)
review = JobReview.objects.create(job=job, customer=customer, professional=prof, rating=5)

try:
    print("hasattr review:", hasattr(job, 'review'))
    print("review rating:", job.review.rating)
except Exception as e:
    print("Exception:", type(e))

# cleanup
job.delete()
customer.delete()
prof.delete()

