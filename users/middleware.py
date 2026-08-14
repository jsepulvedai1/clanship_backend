import logging
import graphql_jwt.utils
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()

class SingleSessionMiddleware(object):
    def resolve(self, next, root, info, **args):
        request = info.context
        if hasattr(request, 'META'):
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
                    except Exception as e:
                        if "SESSION_INVALIDATED" in str(e):
                            raise e

        return next(root, info, **args)
