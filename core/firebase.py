import os
import logging
import firebase_admin
from firebase_admin import credentials, messaging

logger = logging.getLogger(__name__)

# Firebase App Initialization flag
_firebase_initialized = False

def initialize_firebase():
    global _firebase_initialized

    cred = None

    # 1. Try to load from firebase-credentials.json file FIRST
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cred_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS') or os.path.join(project_root, 'firebase-credentials.json')

    if os.path.exists(cred_path):
        try:
            import json
            with open(cred_path, 'r') as f:
                cred_info = json.load(f)
                logger.info(
                    f"Loading Certificate from {cred_path}: client_email={cred_info.get('client_email')}, "
                    f"project_id={cred_info.get('project_id')}, private_key_id={cred_info.get('private_key_id')}"
                )
            cred = credentials.Certificate(cred_path)
            try:
                google_cred = cred.get_credential()
                import google.auth.transport.requests
                req = google.auth.transport.requests.Request()
                google_cred.refresh(req)
                logger.info(f"Successfully obtained Google OAuth2 Access Token! Token starts with: {google_cred.token[:15]}...")
            except Exception as auth_err:
                logger.error(f"Failed to fetch Google OAuth2 Access Token: {auth_err}", exc_info=True)
            logger.info(f"Loaded Firebase credentials from file at {cred_path}.")
        except Exception as e:
            logger.error(f"Error loading Firebase credentials file at {cred_path}: {e}")

    # 2. If no file, try to load from raw JSON string in environment variable
    if not cred:
        raw_json = os.environ.get('FIREBASE_CREDENTIALS_JSON')
        if raw_json and raw_json.strip().startswith('{'):
            try:
                import json
                cred_dict = json.loads(raw_json)
                cred = credentials.Certificate(cred_dict)
                logger.info("Loaded Firebase credentials from FIREBASE_CREDENTIALS_JSON env var.")
            except Exception as e:
                logger.error(f"Error parsing FIREBASE_CREDENTIALS_JSON env var: {e}")

    if cred:
        try:
            # Delete any previously initialized app instance (e.g. unauthenticated)
            if firebase_admin._apps:
                for app_name, app_instance in list(firebase_admin._apps.items()):
                    try:
                        firebase_admin.delete_app(app_instance)
                    except Exception:
                        pass

            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            logger.info("Firebase Admin initialized successfully with Certificate.")
            return True
        except Exception as e:
            logger.error(f"Error initializing Firebase app with Certificate: {e}")
            return False
    else:
        logger.warning("No valid Firebase credentials found (firebase-credentials.json or env var). Push notifications will run in SIMULATED mode.")
        return False


def send_push_notification(fcm_token, title, body, data=None):
    if not fcm_token:
        return False

    is_initialized = initialize_firebase()
    if not is_initialized:
        logger.info(
            f"[SIMULATED PUSH] Token: {fcm_token} | Title: {title} | Body: {body} | Data: {data}"
        )
        # We print it to standard output as well for easy debugging
        print(f"\n📢 [SIMULATED PUSH] Token: {fcm_token}\n🔔 Title: {title}\n📝 Body: {body}\n📦 Data: {data}\n")
        return True

    try:
        # Ensure values in data dict are strings
        str_data = {}
        if data:
            for k, v in data.items():
                str_data[str[k] if not isinstance(k, str) else k] = str(v)

        message = messaging.Message(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=str_data,
            token=fcm_token,
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default",
                        badge=1,
                    ),
                ),
            ),
        )
        response = messaging.send(message)
        logger.info(f"Successfully sent Firebase message: {response}")
        return True
    except Exception as e:
        logger.exception(f"Error sending Firebase notification: {e}")
        # Clean up unregistered or invalid tokens
        err_msg = str(e).lower()
        if "unregistered" in err_msg or "registration-token-not-registered" in err_msg or "invalid-argument" in err_msg:
            try:
                from users.models import UserDevice
                UserDevice.objects.filter(fcm_token=fcm_token).delete()
                logger.info(f"Cleaned up invalid/unregistered FCM token: {fcm_token}")
            except Exception as clean_err:
                logger.error(f"Error cleaning up FCM token: {clean_err}")
        return False


def send_user_push_notification(user, title, body, data=None):
    """
    Sends a push notification to all active devices of the given user.
    """
    if not user:
        return False

    # Get all active tokens from UserDevice
    from users.models import UserDevice
    tokens = list(UserDevice.objects.filter(user=user).values_list('fcm_token', flat=True))

    # Add legacy token for backwards compatibility if not already present
    if user.fcm_token and user.fcm_token not in tokens:
        tokens.append(user.fcm_token)

    if not tokens:
        logger.info(f"No FCM tokens found for user {user.username}. Skipping push notification.")
        return False

    success = False
    for token in tokens:
        res = send_push_notification(token, title, body, data)
        if res:
            success = True

    return success

