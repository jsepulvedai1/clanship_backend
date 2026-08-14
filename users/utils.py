import uuid
import graphql_jwt.utils

def jwt_payload_handler(user, context=None):
    """
    Generador personalizado de payload JWT que garantiza la inclusión de
    app_type y session_key para el control estricto de sesión única.
    """
    payload = graphql_jwt.utils.jwt_payload(user, context)
    
    app_type = 'CLIENT'
    if context:
        if hasattr(context, '_app_type') and context._app_type:
            app_type = str(context._app_type).upper()
        elif hasattr(context, 'headers'):
            header_app_type = context.headers.get('X-App-Type') or context.headers.get('App-Type')
            if header_app_type:
                app_type = str(header_app_type).upper()

    payload['app_type'] = app_type

    if app_type == 'TRADESMAN':
        if not user.tradesman_session_key:
            user.tradesman_session_key = str(uuid.uuid4())
            user.save(update_fields=['tradesman_session_key'])
        payload['session_key'] = user.tradesman_session_key
    else:
        if not user.client_session_key:
            user.client_session_key = str(uuid.uuid4())
            user.save(update_fields=['client_session_key'])
        payload['session_key'] = user.client_session_key

    return payload
