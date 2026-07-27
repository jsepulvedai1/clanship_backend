import graphql_jwt

class SingleSessionMiddleware(object):
    def resolve(self, next, root, info, **args):
        request = info.context
        if hasattr(request, 'META'):
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if auth_header and auth_header.startswith('JWT '):
                token = auth_header.split(' ')[1]
                try:
                    payload = graphql_jwt.utils.jwt_decode(token)
                    app_type = payload.get('app_type')
                    session_key = payload.get('session_key')
                    
                    user = getattr(request, 'user', None)
                    if user and user.is_authenticated and app_type and session_key:
                        if app_type == 'TRADESMAN':
                            if user.tradesman_session_key and user.tradesman_session_key != session_key:
                                raise Exception("SESSION_INVALIDATED: Tu sesión ha sido iniciada en otro dispositivo.")
                        elif app_type == 'CLIENT':
                            if user.client_session_key and user.client_session_key != session_key:
                                raise Exception("SESSION_INVALIDATED: Tu sesión ha sido iniciada en otro dispositivo.")
                except Exception as e:
                    if "SESSION_INVALIDATED" in str(e):
                        raise e

        return next(root, info, **args)
