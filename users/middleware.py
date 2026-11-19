import logging
import graphql_jwt.utils
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()

class SingleSessionMiddleware(object):
    def resolve(self, next, root, info, **args):
        request = info.context
        if hasattr(request, 'META') and not getattr(request, '_single_session_validated', False):
            request._single_session_validated = True

            # Detectar y normalizar plataforma desde headers HTTP
            raw_platform = (
                request.META.get('HTTP_X_PLATFORM') or 
                request.META.get('HTTP_PLATFORM') or 
                ''
            ).strip().upper()

            platform_val = None
            if 'IOS' in raw_platform or 'IPHONE' in raw_platform or 'IPAD' in raw_platform:
                platform_val = 'IOS'
            elif 'ANDROID' in raw_platform:
                platform_val = 'ANDROID'
            elif 'WEB' in raw_platform:
                platform_val = 'WEB'

            if platform_val:
                setattr(request, '_platform', platform_val)

            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if auth_header and (' ' in auth_header):
                parts = auth_header.split(' ', 1)
                prefix = parts[0].upper()
                if prefix in ['JWT', 'BEARER']:
                    token = parts[1].strip()
                    try:
                        payload = graphql_jwt.utils.jwt_decode(token)
                        app_type = payload.get('app_type', 'CLIENT').upper()
                        session_key = payload.get('session_key')

                        # Attach app_type to request for downstream resolvers
                        setattr(request, '_app_type', app_type)

                        # Si el token tenía plataforma grabada y no vino header, usar la del token
                        if not platform_val and payload.get('platform'):
                            token_platform = str(payload.get('platform')).strip().upper()
                            if token_platform in ['IOS', 'ANDROID', 'WEB']:
                                platform_val = token_platform
                                setattr(request, '_platform', platform_val)

                        # Obtener usuario directamente desde el payload JWT
                        user = None
                        try:
                            user = graphql_jwt.utils.get_user_by_payload(payload)
                        except Exception:
                            username = payload.get(User.USERNAME_FIELD) or payload.get('username')
                            if username:
                                user = User.objects.filter(username__iexact=username).first()

                        if user and user.is_authenticated and session_key:
                            if app_type == 'TRADESMAN':
                                if user.tradesman_session_key and user.tradesman_session_key != session_key:
                                    logger.warning(f"[SingleSession] Sesión invalidada para maestro {user.username} (Token: {session_key[:8]}, BD: {user.tradesman_session_key[:8]})")
                                    raise Exception("SESSION_INVALIDATED: Tu sesión ha sido iniciada en otro dispositivo.")
                            else:
                                if user.client_session_key and user.client_session_key != session_key:
                                    logger.warning(f"[SingleSession] Sesión invalidada para cliente {user.username} (Token: {session_key[:8]}, BD: {user.client_session_key[:8]})")
                                    raise Exception("SESSION_INVALIDATED: Tu sesión ha sido iniciada en otro dispositivo.")

                            # Actualizar last_platform y last_active_at con throttling (máximo una vez cada 2 minutos)
                            now = timezone.now()
                            should_update = False
                            update_fields = []
                            if platform_val and user.last_platform != platform_val:
                                user.last_platform = platform_val
                                update_fields.append('last_platform')
                                should_update = True
                            if not user.last_active_at or (now - user.last_active_at).total_seconds() > 120:
                                user.last_active_at = now
                                update_fields.append('last_active_at')
                                should_update = True

                            if should_update:
                                try:
                                    user.save(update_fields=update_fields)
                                except Exception as save_err:
                                    logger.debug(f"Error saving last_platform/last_active_at: {save_err}")
                    except Exception as e:
                        if "SESSION_INVALIDATED" in str(e):
                            raise e

        return next(root, info, **args)
