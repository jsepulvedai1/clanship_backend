import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from users.models import User, ProfessionalProfile
from jobs.models import Job, JobReview

user1 = User.objects.create_user(username='test_customer', password='123', user_type='CUSTOMER')
user2 = User.objects.create_user(username='test_prof', password='123', user_type='TRADESMAN')
prof_profile = ProfessionalProfile.objects.create(user=user2)

job = Job.objects.create(customer=user1, professional=user2, status='FINISHED')
print("Profile rating before:", prof_profile.rating)

review = JobReview.objects.create(job=job, customer=user1, professional=user2, rating=5)

prof_profile.refresh_from_db()
print("Profile rating after review created:", prof_profile.rating)

job.delete()
user1.delete()
user2.delete()
