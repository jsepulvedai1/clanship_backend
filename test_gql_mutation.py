import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from graphene.test import Client
from core.schema import schema
from users.models import User
from jobs.models import Job

customer = User.objects.create_user(username='cust_gql_2', password='123', user_type='CUSTOMER')
prof = User.objects.create_user(username='prof_gql_2', password='123', user_type='TRADESMAN')
job = Job.objects.create(customer=customer, professional=prof, status=Job.Status.FINISHED)

class DummyContext:
    def __init__(self, user):
        self.user = user

client = Client(schema)
query = """
mutation RateJob($jobId: Int!, $rating: Int!, $comment: String) {
  rateJob(jobId: $jobId, rating: $rating, comment: $comment) {
    success
    job {
      id
      hasBeenReviewed
      review {
        rating
        comment
      }
      hasClaim
      finalPrice
      tradesmanComments
      finishedPhotosUrls
      claim {
        statusDisplay
      }
    }
  }
}
"""
variables = {
    "jobId": job.id,
    "rating": 5,
    "comment": "Perfect"
}

executed = client.execute(query, variable_values=variables, context_value=DummyContext(customer))
print(executed)

job.delete()
customer.delete()
prof.delete()
