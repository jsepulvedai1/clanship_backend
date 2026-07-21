from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from jobs.models import Job
from core.firebase import send_user_push_notification

class Command(BaseCommand):
    help = "Envía notificaciones de recordatorio de visitas programadas basadas en el tiempo configurable de aviso previo"

    def handle(self, *args, **options):
        now = timezone.localtime(timezone.now())
        self.stdout.write(f"Iniciando verificación de recordatorios de visita a las {now}")

        # Obtener todos los trabajos acordados que tienen fecha y hora programada y no han enviado recordatorio
        jobs = Job.objects.filter(
            status=Job.Status.AGREED,
            lead_notification_sent=False,
            scheduled_date__isnull=False,
            scheduled_time__isnull=False
        )

        sent_count = 0

        for job in jobs:
            try:
                # Combinar fecha y hora
                visit_naive = datetime.combine(job.scheduled_date, job.scheduled_time)
                # Hacer aware el datetime combinando el timezone actual
                visit_dt = timezone.make_aware(visit_naive, timezone.get_current_timezone())
                
                # Calcular la diferencia en minutos
                time_difference = visit_dt - now
                minutes_until_visit = time_difference.total_seconds() / 60.0

                # Si está dentro de la ventana del tiempo de aviso previo programado y no ha pasado
                if 0 <= minutes_until_visit <= job.notification_lead_minutes:
                    self.stdout.write(f"Enviando recordatorio para Trabajo ID {job.id} (visita en {int(minutes_until_visit)} minutos)")

                    # Notificar al cliente
                    cust = job.customer
                    if cust:
                        prof_name = job.professional.get_full_name() or job.professional.username
                        send_user_push_notification(
                            user=cust,
                            title="Recordatorio de Visita",
                            body=f"Tu visita con el profesional {prof_name} es en {int(minutes_until_visit)} minutos.",
                            data={"event": "visit_reminder", "job_id": job.id}
                        )

                    # Notificar al profesional (maestro)
                    prof = job.professional
                    if prof:
                        cust_name = job.customer.get_full_name() or job.customer.username
                        send_user_push_notification(
                            user=prof,
                            title="Recordatorio de Visita",
                            body=f"Tu visita con el cliente {cust_name} es en {int(minutes_until_visit)} minutos.",
                            data={"event": "visit_reminder", "job_id": job.id}
                        )

                    # Marcar recordatorio como enviado
                    job.lead_notification_sent = True
                    job.save()
                    sent_count += 1
            except Exception as e:
                self.stderr.write(f"Error procesando Trabajo ID {job.id}: {e}")

        self.stdout.write(self.style.SUCCESS(f"Proceso finalizado. Recordatorios enviados: {sent_count}"))

