import logging
from celery import shared_task
from django.contrib.auth import get_user_model
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from core.firebase import send_user_push_notification

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def send_user_push_notification_async(self, user_id, title, body, data=None):
    """
    Tarea asíncrona de Celery para enviar notificaciones push a través de Firebase.
    Desacopla las llamadas HTTP a FCM del ciclo de vida de las solicitudes HTTP/Signals.
    """
    User = get_user_model()
    try:
        user = User.objects.filter(pk=user_id).first()
        if user:
            send_user_push_notification(user=user, title=title, body=body, data=data)
            logger.info(f"[Celery] Push notification enviada exitosamente a usuario {user_id}")
    except Exception as e:
        logger.error(f"[Celery] Error enviando push notification a usuario {user_id}: {e}")
        try:
            self.retry(exc=e)
        except Exception:
            pass


@shared_task(bind=True, max_retries=2, default_retry_delay=3)
def process_job_saved_notifications(self, job_id, created, previous_status=None):
    """
    Tarea asíncrona de Celery para procesar notificaciones WebSocket y FCM al guardar/actualizar un Job.
    """
    from jobs.models import Job
    try:
        job = Job.objects.select_related('customer', 'professional', 'cancelled_by').filter(pk=job_id).first()
        if not job:
            return

        # 1. Notificaciones en tiempo real por WebSockets
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                for user in [job.customer, job.professional]:
                    if user:
                        cancelled_by_name = (job.cancelled_by.get_full_name() or job.cancelled_by.username) if job.cancelled_by else None
                        async_to_sync(channel_layer.group_send)(
                            f"user_{user.id}",
                            {
                                "type": "job_notification",
                                "event": "job_created" if created else "job_updated",
                                "job_id": job.id,
                                "status": job.status,
                                "message": "Nuevo trabajo recibido" if created else "El estado del trabajo ha cambiado",
                                "cancellation_reason": job.cancellation_reason or "",
                                "cancelled_by": cancelled_by_name or "",
                            }
                        )

                # Si el trabajo tiene sala de chat asociada, emitir a la sala en tiempo real
                from chat.models import ChatRoom
                chat_room = ChatRoom.objects.filter(customer=job.customer, professional=job.professional).first()
                if chat_room:
                    cancelled_by_str = (job.cancelled_by.get_full_name() or job.cancelled_by.username) if job.cancelled_by else None
                    async_to_sync(channel_layer.group_send)(
                        f"chat_{chat_room.id}",
                        {
                            "type": "job_status_changed",
                            "event": "JOB_STATUS_CHANGED",
                            "job_id": job.id,
                            "new_status": job.status,
                            "cancellation_reason": job.cancellation_reason,
                            "cancelled_by": cancelled_by_str
                        }
                    )
        except Exception as ws_err:
            logger.error(f"[Celery] Error en WebSocket job notification: {ws_err}")

        # 2. Notificaciones push por Firebase Messaging (FCM)
        try:
            if created:
                prof = job.professional
                if prof:
                    client_name = job.customer.get_full_name() or job.customer.username
                    send_user_push_notification(
                        user=prof,
                        title="Nueva solicitud de trabajo",
                        body=f"Tienes una nueva solicitud de {client_name}.",
                        data={"event": "job_created", "job_id": str(job.id)}
                    )
            elif job.status == Job.Status.CANCELLED:
                if job.cancelled_by == job.customer:
                    prof = job.professional
                    if prof:
                        client_name = job.customer.get_full_name() or job.customer.username
                        reason_text = f" Motivo: {job.cancellation_reason}" if job.cancellation_reason else ""
                        send_user_push_notification(
                            user=prof,
                            title="Solicitud Cancelada por el Cliente",
                            body=f"{client_name} ha cancelado la solicitud.{reason_text}",
                            data={"event": "job_cancelled", "job_id": str(job.id)}
                        )
                else:
                    cust = job.customer
                    if cust:
                        prof_name = job.professional.get_full_name() or job.professional.username
                        send_user_push_notification(
                            user=cust,
                            title="Solicitud Rechazada",
                            body=f"Tu solicitud con {prof_name} ha sido cancelada o rechazada.",
                            data={"event": "job_cancelled", "job_id": str(job.id)}
                        )
        except Exception as fcm_err:
            logger.error(f"[Celery] Error en FCM job notification: {fcm_err}")

    except Exception as exc:
        logger.error(f"[Celery] Error procesando job notifications para job {job_id}: {exc}")
        try:
            self.retry(exc=exc)
        except Exception:
            pass


@shared_task(bind=True, max_retries=2, default_retry_delay=3)
def process_chat_message_notifications(self, message_id):
    """
    Tarea asíncrona de Celery para procesar notificaciones WebSocket y FCM al enviar un mensaje de chat.
    """
    from chat.models import Message
    try:
        msg = Message.objects.select_related('room__customer', 'room__professional', 'sender').filter(pk=message_id).first()
        if not msg:
            return

        room = msg.room
        recipient = room.professional if msg.sender == room.customer else room.customer
        if not recipient:
            return

        sender_name = msg.sender.get_full_name() or msg.sender.username
        body_text = msg.text or ""
        if msg.message_type == 'IMAGE':
            body_text = "📷 Foto"
        elif msg.message_type == 'AUDIO':
            body_text = "🎤 Mensaje de voz"

        # 1. FCM Push Notification
        try:
            send_user_push_notification(
                user=recipient,
                title=f"Mensaje de {sender_name}",
                body=body_text,
                data={
                    "event": "chat_message",
                    "room_id": str(room.id),
                    "job_id": str(room.job.id) if room.job else ""
                }
            )
        except Exception as fcm_err:
            logger.error(f"[Celery] Error enviando FCM de chat: {fcm_err}")

        # 2. WebSocket User Notification
        try:
            channel_layer = get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    f'user_{recipient.id}',
                    {
                        'type': 'job_notification',
                        'event': 'new_message',
                        'job_id': str(room.job.id) if room.job else "",
                        'message': f"Mensaje de {sender_name}: {body_text}"
                    }
                )
        except Exception as ws_err:
            logger.error(f"[Celery] Error enviando WS de chat: {ws_err}")

    except Exception as exc:
        logger.error(f"[Celery] Error procesando chat notifications para message {message_id}: {exc}")
        try:
            self.retry(exc=exc)
        except Exception:
            pass
