from users.models import User, ProfessionalProfile
from jobs.models import Job
from chat.models import Message
from django.db.models import Sum

def dashboard_callback(request, context):
    """
    Inyecta estadísticas dinámicas de Clanship en el dashboard de django-unfold.
    """
    total_users = User.objects.count()
    total_customers = User.objects.filter(user_type=User.UserType.CUSTOMER).count()
    total_professionals = User.objects.filter(user_type=User.UserType.PROFESSIONAL).count()
    
    total_jobs = Job.objects.count()
    active_jobs = Job.objects.filter(
        status__in=[Job.Status.REQUESTED, Job.Status.AGREED, Job.Status.IN_VISIT]
    ).count()
    completed_jobs = Job.objects.filter(status=Job.Status.FINISHED).count()
    cancelled_jobs = Job.objects.filter(status=Job.Status.CANCELLED).count()

    total_revenue = Job.objects.filter(status=Job.Status.FINISHED).aggregate(total=Sum('agreed_price'))['total'] or 0
    
    verified_professionals = ProfessionalProfile.objects.filter(is_verified=True).count()
    unverified_professionals = total_professionals - verified_professionals

    recent_jobs = Job.objects.order_by('-created_at')[:5]
    recent_messages = Message.objects.order_by('-created_at')[:5]

    context.update({
        "total_users": total_users,
        "total_customers": total_customers,
        "total_professionals": total_professionals,
        "total_jobs": total_jobs,
        "active_jobs": active_jobs,
        "completed_jobs": completed_jobs,
        "cancelled_jobs": cancelled_jobs,
        "total_revenue": total_revenue,
        "verified_professionals": verified_professionals,
        "unverified_professionals": unverified_professionals,
        "recent_jobs": recent_jobs,
        "recent_messages": recent_messages,
    })
    return context
