import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from users.models import User, ProfessionalProfile

print("All Users:", User.objects.count())
for u in User.objects.all():
    print(f"  User: {u.email} type={u.user_type}")

print("Profiles:", ProfessionalProfile.objects.count())
for p in ProfessionalProfile.objects.all():
    print(f"  Profile: {p.user.email} plan={p.plan.name if p.plan else 'None'} jobs={p.user.professional_jobs.count()}")
