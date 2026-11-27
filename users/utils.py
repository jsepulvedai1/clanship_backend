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

    platform = None
    if context:
        if hasattr(context, '_platform') and context._platform:
            platform = str(context._platform).upper()
        elif hasattr(context, 'headers'):
            header_platform = context.headers.get('X-Platform') or context.headers.get('Platform')
            if header_platform:
                platform = str(header_platform).upper()
    if platform:
        payload['platform'] = platform

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


def issue_user_tokens(user, app_type='TRADESMAN', platform=None, context=None):
    """
    Genera tokens de acceso JWT y refresh token para un usuario,
    actualizando la sesión única según el tipo de aplicación (TRADESMAN o CLIENT).
    """
    import uuid
    from graphql_jwt.shortcuts import get_token, create_refresh_token
    from graphql_jwt.refresh_token.models import RefreshToken

    app_type_str = str(app_type or 'TRADESMAN').upper()
    session_key = str(uuid.uuid4())

    platform_str = str(platform).upper() if platform else None
    if not platform_str and context:
        platform_str = getattr(context, '_platform', None)

    update_fields = []
    if app_type_str == 'TRADESMAN':
        user.tradesman_session_key = session_key
        update_fields.append('tradesman_session_key')
    else:
        user.client_session_key = session_key
        update_fields.append('client_session_key')

    if platform_str in ['IOS', 'ANDROID', 'WEB']:
        user.last_platform = platform_str
        update_fields.append('last_platform')

    from django.utils import timezone
    user.last_active_at = timezone.now()
    update_fields.append('last_active_at')

    user.save(update_fields=update_fields)

    class AppContext:
        def __init__(self, base_ctx, app_t, plat=None):
            self._app_type = app_t
            self._platform = plat
            if base_ctx and hasattr(base_ctx, 'headers'):
                self.headers = base_ctx.headers

    ctx = AppContext(context, app_type_str, platform_str)
    token = get_token(user, ctx)
    refresh_token = create_refresh_token(user)

    try:
        RefreshToken.objects.filter(user=user).exclude(token=refresh_token.get_token()).delete()
    except Exception:
        pass

    return token, refresh_token.get_token()


UNSET = object()


def normalize_phone_number(raw_phone):
    """
    Limpia espacios, guiones, paréntesis y puntos de un número telefónico.
    """
    import re
    if raw_phone is None:
        return ''
    return re.sub(r'[\s\-\(\)\.]+', '', str(raw_phone).strip())


def ensure_municipality_capacity(municipality, *, exclude_profile_id=None, exclude_user_id=None):
    """
    Verifica que la municipalidad aún tenga cupos disponibles antes de asociar un maestro.
    Lanza UserFacingError con código MUNICIPALITY_LIMIT_REACHED si alcanzó su límite.
    """
    if municipality is None or municipality.max_professionals is None:
        return
    if not municipality.has_available_slots(
        exclude_profile_id=exclude_profile_id,
        exclude_user_id=exclude_user_id,
    ):
        from core.exceptions import UserFacingError
        raise UserFacingError(
            f'La municipalidad "{municipality.name}" alcanzó el límite máximo de {municipality.max_professionals} maestros.',
            code='MUNICIPALITY_LIMIT_REACHED',
        )


def admin_update_user_fields(
    target_user,
    *,
    email=UNSET,
    clear_email=False,
    phone_number=UNSET,
    clear_phone=False,
    first_name=UNSET,
    last_name=UNSET,
    username=UNSET,
    address=UNSET,
    latitude=UNSET,
    longitude=UNSET,
    is_active=UNSET,
    is_available=UNSET,
    is_emergency=UNSET,
    user_type=UNSET,
    bio=UNSET,
    hourly_rate=UNSET,
    service_radius=UNSET,
    rating=UNSET,
    specialty_id=UNSET,
    plan_id=UNSET,
    municipality_id=UNSET,
    clear_municipality=False,
    referral_code=UNSET,
    facebook_url=UNSET,
    instagram_url=UNSET,
    tiktok_url=UNSET,
):
    """
    Actualiza de forma segura y validada los datos de contacto y perfil de un usuario
    (cliente, maestro o administrador) desde el gestor de Clanship (clanship-admin).
    Valida formato y unicidad de correo y teléfono, sincronizando username cuando corresponde.
    """
    import re
    from decimal import Decimal, InvalidOperation
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email
    from django.db import IntegrityError, transaction
    from django.db.models import Q
    from core.exceptions import UserFacingError
    from users.models import User, Specialty, SubscriptionPlan, ProfessionalProfile, Municipality

    old_email = (target_user.email or '').strip().lower()
    old_username = (target_user.username or '').strip()

    explicit_username = None
    if username is not UNSET and username is not None:
        clean_username = str(username).strip()
        if clean_username and clean_username.lower() != old_username.lower():
            if len(clean_username) > 150:
                raise UserFacingError(
                    'El nombre de usuario no puede superar los 150 caracteres.',
                    code='USERNAME_TOO_LONG'
                )
            if User.objects.filter(username__iexact=clean_username).exclude(id=target_user.id).exists():
                raise UserFacingError(
                    'El nombre de usuario ya está registrado por otro usuario.',
                    code='USERNAME_ALREADY_EXISTS'
                )
            explicit_username = clean_username

    # 1. Correo electrónico
    if clear_email:
        target_user.email = ''
    elif email is not UNSET and email is not None:
        clean_email = str(email).strip().lower()
        if not clean_email:
            # Si ya tenía correo y se envió vacío explícitamente, limpiar solo si cambió
            if old_email:
                target_user.email = ''
        else:
            try:
                validate_email(clean_email)
            except ValidationError:
                raise UserFacingError(
                    'El formato del correo electrónico no es válido.',
                    code='EMAIL_INVALID'
                )

            conflict_user = User.objects.filter(
                Q(email__iexact=clean_email) | Q(username__iexact=clean_email)
            ).exclude(id=target_user.id).first()
            if conflict_user:
                conflict_name = conflict_user.get_full_name() or conflict_user.username
                raise UserFacingError(
                    f'El correo electrónico ya está registrado por otro usuario ({conflict_name}).',
                    code='EMAIL_ALREADY_REGISTERED'
                )

            target_user.email = clean_email

            # Sincronizar username con el nuevo correo cuando el usuario no es admin/staff
            # y su username seguía al correo o era un identificador autogenerado
            is_admin_account = (
                target_user.is_staff
                or target_user.is_superuser
                or target_user.user_type == User.UserType.ADMIN
            )
            if explicit_username is None and not is_admin_account:
                old_user_lower = old_username.lower()
                should_sync_username = (
                    (bool(old_email) and old_user_lower == old_email)
                    or (
                        not old_email
                        and (
                            '@' in old_user_lower
                            or old_user_lower.startswith(('apple_', 'google_', 'cliente_', 'maestro_', 'user_'))
                        )
                    )
                    or (target_user.auth_provider == User.AuthProvider.EMAIL and '@' in old_user_lower)
                )
                if should_sync_username:
                    target_user.username = clean_email

    if explicit_username is not None:
        target_user.username = explicit_username

    # 2. Teléfono
    if clear_phone:
        target_user.phone_number = None
    elif phone_number is not UNSET:
        clean_phone = normalize_phone_number(phone_number)
        if not clean_phone:
            target_user.phone_number = None
        else:
            if not re.fullmatch(r'\+?\d+', clean_phone):
                raise UserFacingError(
                    'El número de teléfono solo puede contener dígitos y el prefijo + opcional.',
                    code='PHONE_INVALID'
                )
            digits_only = clean_phone.lstrip('+')
            if len(digits_only) < 8:
                raise UserFacingError(
                    'El número de teléfono ingresado es demasiado corto (mínimo 8 dígitos).',
                    code='PHONE_INVALID'
                )
            if len(clean_phone) > 15:
                raise UserFacingError(
                    'El número de teléfono no puede superar los 15 caracteres.',
                    code='PHONE_TOO_LONG'
                )

            phone_variants = get_phone_variants(clean_phone)
            conflict_user = User.objects.filter(
                phone_number__in=phone_variants
            ).exclude(id=target_user.id).first()
            if conflict_user:
                conflict_name = conflict_user.get_full_name() or conflict_user.username
                raise UserFacingError(
                    f'El número de teléfono ya está registrado por otro usuario ({conflict_name}).',
                    code='PHONE_ALREADY_REGISTERED'
                )
            target_user.phone_number = clean_phone

    # 3. Datos básicos de usuario (opcionales)
    if first_name is not UNSET and first_name is not None:
        clean_fn = str(first_name).strip()
        if len(clean_fn) > 30:
            raise UserFacingError(
                'El nombre no puede tener más de 30 caracteres.',
                code='FIRST_NAME_TOO_LONG'
            )
        target_user.first_name = clean_fn

    if last_name is not UNSET and last_name is not None:
        clean_ln = str(last_name).strip()
        if len(clean_ln) > 30:
            raise UserFacingError(
                'El apellido no puede tener más de 30 caracteres.',
                code='LAST_NAME_TOO_LONG'
            )
        target_user.last_name = clean_ln

    if address is not UNSET:
        target_user.address = str(address).strip() if address else ''

    if latitude is not UNSET:
        if latitude is None or str(latitude).strip() == '':
            target_user.latitude = None
        else:
            try:
                target_user.latitude = Decimal(str(latitude))
            except (InvalidOperation, ValueError):
                raise UserFacingError('Latitud inválida.', code='INVALID_LATITUDE')

    if longitude is not UNSET:
        if longitude is None or str(longitude).strip() == '':
            target_user.longitude = None
        else:
            try:
                target_user.longitude = Decimal(str(longitude))
            except (InvalidOperation, ValueError):
                raise UserFacingError('Longitud inválida.', code='INVALID_LONGITUDE')

    if is_active is not UNSET and is_active is not None:
        target_user.is_active = bool(is_active)

    if is_available is not UNSET and is_available is not None:
        target_user.is_available = bool(is_available)

    if is_emergency is not UNSET and is_emergency is not None:
        target_user.is_emergency = bool(is_emergency)

    if is_available is not UNSET or is_emergency is not UNSET:
        if not target_user.is_available:
            target_user.is_emergency = False
        elif target_user.is_emergency:
            target_user.is_available = True

    if user_type is not UNSET and user_type is not None:
        ut = str(user_type).strip().upper()
        if ut in User.UserType.values:
            target_user.user_type = ut

    # 4. Datos opcionales del perfil profesional (si existe)
    prof = getattr(target_user, 'professional_profile', None)
    prof_dirty = False
    if prof is not None:
        if address is not UNSET:
            prof.address = target_user.address
            prof_dirty = True
        if latitude is not UNSET:
            prof.latitude = target_user.latitude
            prof_dirty = True
        if longitude is not UNSET:
            prof.longitude = target_user.longitude
            prof_dirty = True
        if bio is not UNSET:
            prof.bio = str(bio).strip()[:500] if bio else ''
            prof_dirty = True
        if hourly_rate is not UNSET:
            if hourly_rate is None or str(hourly_rate).strip() == '':
                prof.hourly_rate = None
            else:
                try:
                    prof.hourly_rate = Decimal(str(hourly_rate))
                except (InvalidOperation, ValueError):
                    raise UserFacingError('Tarifa por hora inválida.', code='INVALID_HOURLY_RATE')
            prof_dirty = True
        if service_radius is not UNSET and service_radius is not None:
            try:
                prof.service_radius = max(1, int(service_radius))
                prof_dirty = True
            except (ValueError, TypeError):
                raise UserFacingError('Radio de servicio inválido.', code='INVALID_RADIUS')
        if rating is not UNSET and rating is not None:
            try:
                prof.rating = max(0.0, min(5.0, float(rating)))
                prof_dirty = True
            except (ValueError, TypeError):
                raise UserFacingError('Calificación inválida.', code='INVALID_RATING')
        if specialty_id is not UNSET and specialty_id is not None and str(specialty_id).strip() != '':
            spec = Specialty.objects.filter(id=specialty_id).first()
            if spec:
                prof.specialty = spec
                prof_dirty = True
        if plan_id is not UNSET and plan_id is not None and str(plan_id).strip() != '':
            plan = SubscriptionPlan.objects.filter(id=plan_id).first()
            if plan:
                prof.plan = plan
                prof_dirty = True
        if clear_municipality:
            prof.municipality = None
            prof_dirty = True
        elif municipality_id is not UNSET:
            if municipality_id is None or str(municipality_id).strip() == '':
                prof.municipality = None
                prof_dirty = True
            else:
                municipality = Municipality.objects.filter(id=municipality_id).first()
                if not municipality:
                    raise UserFacingError('La municipalidad seleccionada no existe.', code='MUNICIPALITY_NOT_FOUND')
                if prof.municipality_id != municipality.id:
                    ensure_municipality_capacity(municipality, exclude_profile_id=prof.id)
                prof.municipality = municipality
                prof_dirty = True
        if referral_code is not UNSET:
            clean_ref = str(referral_code).strip().upper() if referral_code else None
            if clean_ref:
                if ProfessionalProfile.objects.filter(referral_code__iexact=clean_ref).exclude(id=prof.id).exists():
                    raise UserFacingError(
                        'El código de asociado ya está en uso por otro maestro.',
                        code='REFERRAL_CODE_EXISTS'
                    )
            prof.referral_code = clean_ref or None
            prof_dirty = True
        if facebook_url is not UNSET:
            prof.facebook_url = str(facebook_url).strip() or None
            prof_dirty = True
        if instagram_url is not UNSET:
            prof.instagram_url = str(instagram_url).strip() or None
            prof_dirty = True
        if tiktok_url is not UNSET:
            prof.tiktok_url = str(tiktok_url).strip() or None
            prof_dirty = True

    try:
        with transaction.atomic():
            target_user.save()
            if prof is not None and prof_dirty:
                prof.save()
                if specialty_id is not UNSET and prof.specialty_id:
                    if not prof.specialties.filter(id=prof.specialty_id).exists():
                        prof.specialties.add(prof.specialty)
    except IntegrityError as e:
        err_lower = str(e).lower()
        if 'phone' in err_lower:
            raise UserFacingError(
                'El número de teléfono ya está registrado por otro usuario.',
                code='PHONE_ALREADY_REGISTERED'
            )
        if 'email' in err_lower or 'username' in err_lower:
            raise UserFacingError(
                'El correo electrónico o nombre de usuario ya está registrado por otro usuario.',
                code='EMAIL_ALREADY_REGISTERED'
            )
        if 'referral_code' in err_lower:
            raise UserFacingError(
                'El código de asociado ya está en uso por otro maestro.',
                code='REFERRAL_CODE_EXISTS'
            )
        raise UserFacingError('No se pudieron guardar los cambios por un conflicto de datos.', code='INTEGRITY_ERROR')

    return target_user
