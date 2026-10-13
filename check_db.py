import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()
from jobs.models import JobReview
print("Total reviews:", JobReview.objects.count())
for r in JobReview.objects.all()[:5]:
    print(r.id, r.rating, r.professional.username)
