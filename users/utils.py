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


def get_phone_variants(phone):
    """
    Genera todas las variantes posibles de un número telefónico (con/sin prefijo país +56,
    con/sin símbolo '+', con/sin código de área) para validar unicidad de forma robusta.
    """
    if not phone:
        return []
    clean = str(phone).strip().replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    if not clean:
        return []
    variants = {clean}
    if clean.startswith('+'):
        raw = clean[1:]
        variants.add(raw)
        if raw.startswith('56'):
            variants.add(raw[2:])
            variants.add('+' + raw[2:])
    else:
        variants.add('+' + clean)
        if clean.startswith('56'):
            variants.add(clean[2:])
            variants.add('+56' + clean[2:])
        elif len(clean) == 9 and clean.startswith('9'):
            variants.add('+56' + clean)
            variants.add('56' + clean)
    return list(variants)


def issue_user_tokens(user, app_type='TRADESMAN', context=None):
    """
    Genera tokens de acceso JWT y refresh token para un usuario,
    actualizando la sesión única según el tipo de aplicación (TRADESMAN o CLIENT).
    """
    import uuid
    from graphql_jwt.shortcuts import get_token, create_refresh_token
    from graphql_jwt.refresh_token.models import RefreshToken

    app_type_str = str(app_type or 'TRADESMAN').upper()
    session_key = str(uuid.uuid4())

    if app_type_str == 'TRADESMAN':
        user.tradesman_session_key = session_key
        user.save(update_fields=['tradesman_session_key'])
    else:
        user.client_session_key = session_key
        user.save(update_fields=['client_session_key'])

    class AppContext:
        def __init__(self, base_ctx, app_t):
            self._app_type = app_t
            if base_ctx and hasattr(base_ctx, 'headers'):
                self.headers = base_ctx.headers

    ctx = AppContext(context, app_type_str)
    token = get_token(user, ctx)
    refresh_token = create_refresh_token(user)

    try:
        RefreshToken.objects.filter(user=user).exclude(token=refresh_token.get_token()).delete()
    except Exception:
        pass

    return token, refresh_token.get_token()
