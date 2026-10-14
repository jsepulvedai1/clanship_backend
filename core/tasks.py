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
                        event_name = "job_created" if created else ("job_cancelled" if job.status == Job.Status.CANCELLED else "job_updated")
                        msg = "Nuevo trabajo recibido" if created else ("El trabajo ha sido cancelado" if job.status == Job.Status.CANCELLED else "El estado del trabajo ha cambiado")
                        async_to_sync(channel_layer.group_send)(
                            f"user_{user.id}",
                            {
                                "type": "job_notification",
                                "event": event_name,
                                "job_id": str(job.id),
                                "status": job.status,
                                "message": msg,
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


def _calculate_distance_km(lat1, lon1, lat2, lon2):
    import math
    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
        r = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2.0) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2)
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return r * c
    except (ValueError, TypeError):
        return 0.0


@shared_task(bind=True, max_retries=2, default_retry_delay=5)
def process_public_job_created_notifications(self, public_request_id):
    """
    Tarea asíncrona de Celery para notificar a los profesionales/maestros calificados
    por Push (FCM) y WebSockets cuando un cliente publica una nueva cotización/solicitud abierta.
    Aplica los mismos filtros de especialidad y radio de distancia geográfica que la app.
    """
    from jobs.models import PublicJobRequest
    from django.contrib.auth import get_user_model
    from users.models import SystemSetting
    from django.db.models import Q

    try:
        pub_req = PublicJobRequest.objects.select_related('customer', 'specialty').filter(
            pk=public_request_id,
            status=PublicJobRequest.Status.OPEN
        ).first()

        if not pub_req:
            logger.info(f"[Celery] Solicitud pública {public_request_id} no encontrada o no está en estado OPEN.")
            return

        User = get_user_model()

        # 1. Base: profesionales activos con perfil verificado
        queryset = User.objects.filter(
            user_type='PROFESSIONAL',
            is_active=True,
            professional_profile__isnull=False
        ).filter(
            Q(professional_profile__verification_status='APPROVED') |
            Q(professional_profile__is_verified=True)
        ).exclude(id=pub_req.customer_id).select_related('professional_profile').prefetch_related('professional_profile__specialties')

        # 2. Filtrado por especialidad
        if pub_req.specialty_id:
            queryset = queryset.filter(
                Q(professional_profile__specialty_id=pub_req.specialty_id) |
                Q(professional_profile__specialties__id=pub_req.specialty_id)
            ).distinct()

        # 3. Filtrado por distancia (radio de cobertura del maestro vs distancia a la solicitud)
        nationwide_mode = SystemSetting.is_nationwide_coverage_active()
        eligible_professionals = []

        if not nationwide_mode and pub_req.latitude is not None and pub_req.longitude is not None:
            req_lat = float(pub_req.latitude)
            req_lon = float(pub_req.longitude)

            for prof in queryset:
                prof_profile = prof.professional_profile
                if prof_profile and prof_profile.latitude is not None and prof_profile.longitude is not None:
                    prof_lat = float(prof_profile.latitude)
                    prof_lon = float(prof_profile.longitude)
                    max_radius = float(prof_profile.service_radius or 30.0)
                    dist = _calculate_distance_km(prof_lat, prof_lon, req_lat, req_lon)
                    if dist <= max_radius:
                        eligible_professionals.append(prof)
                    else:
                        logger.debug(
                            f"[Celery] Prof {prof.id} fuera de radio: dist={dist:.1f}km > radio={max_radius:.1f}km"
                        )
                else:
                    # Si el profesional no tiene coordenadas registradas en su perfil, incluirlo
                    eligible_professionals.append(prof)
        else:
            # Cobertura nacional activa o la solicitud no tiene coordenadas explícitas
            eligible_professionals = list(queryset)

        logger.info(
            f"[Celery] Notificando nueva cotización #{pub_req.id} a {len(eligible_professionals)} profesionales calificados."
        )

        specialty_name = pub_req.specialty.name if pub_req.specialty else (pub_req.custom_specialty or "su especialidad")
        location_info = f" en {pub_req.address}" if pub_req.address else ""
        title = f"Nueva cotización disponible ({specialty_name})"
        body = f"Cliente solicita presupuesto{location_info}: '{pub_req.title}'. ¡Envía tu cotización ahora!"

        push_data = {
            "event": "new_public_job",
            "public_request_id": str(pub_req.id),
            "title": title,
            "body": body,
            "specialty": specialty_name,
            "click_action": "FLUTTER_NOTIFICATION_CLICK"
        }

        channel_layer = get_channel_layer()

        for prof in eligible_professionals:
            # Enviar Push Notification
            try:
                send_user_push_notification(
                    user=prof,
                    title=title,
                    body=body,
                    data=push_data
                )
            except Exception as push_err:
                logger.error(f"[Celery] Error enviando push a profesional {prof.id}: {push_err}")

            # Enviar WebSocket en tiempo real
            if channel_layer:
                try:
                    async_to_sync(channel_layer.group_send)(
                        f"user_{prof.id}",
                        {
                            "type": "job_notification",
                            "event": "public_job_created",
                            "public_request_id": str(pub_req.id),
                            "message": f"Nueva cotización disponible: {pub_req.title}",
                        }
                    )
                except Exception as ws_err:
                    logger.error(f"[Celery] Error enviando websocket a profesional {prof.id}: {ws_err}")

    except Exception as exc:
        logger.error(f"[Celery] Error procesando notificaciones para solicitud pública {public_request_id}: {exc}")
        try:
            self.retry(exc=exc)
        except Exception:
            pass

