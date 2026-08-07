import os
from pathlib import Path
from datetime import timedelta
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Cargar variables de entorno desde .env (entorno local)
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / '.env')
except ImportError:
    pass

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-clanship-backend-secret-key')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

# Application definition
INSTALLED_APPS = [
    'unfold',
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis', # Descomentado para geolocalización / PostGIS
    
    # Apps de Terceros
    'corsheaders',
    'graphene_django',
    'channels',
    
    # Apps Locales
    'users',
    'clans',
    'jobs',
    'chat',
    
    # GraphQL JWT Refresh Token
    'graphql_jwt.refresh_token.apps.RefreshTokenConfig',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'
ASGI_APPLICATION = 'core.asgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',  # Modificado para soportar PostGIS / GIS
        'NAME': os.environ.get('DB_NAME', 'clanship_db'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'password'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '5432'),
    }
}

if os.environ.get('DATABASE_URL'):
    db_ssl = os.environ.get('DATABASE_SSL_REQUIRE', 'False') == 'True'
    DATABASES['default'] = dj_database_url.config(conn_max_age=600, ssl_require=db_ssl)
    # Forzar el motor postgis si se usa DATABASE_URL
    DATABASES['default']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# Internationalization
LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Esta línea le dice a Django dónde reunir todos los estáticos del proyecto
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Esta línea habilita la compresión y el cacheo de WhiteNoise para que carguen ultra rápido
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Configuración de límites de tamaño para carga de archivos y cuerpos de request (10 MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'users.User'

# CORS Configuration
CORS_ALLOW_ALL_ORIGINS = True

CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', 'http://localhost:3000,http://127.0.0.1:3000').split(',')

# Graphene Configuration
GRAPHENE = {
    'SCHEMA': 'core.schema.schema',
    'MIDDLEWARE': [
        'graphql_jwt.middleware.JSONWebTokenMiddleware',
        'users.middleware.SingleSessionMiddleware',
    ],
}

# JWT Authentication
AUTHENTICATION_BACKENDS = [
    'graphql_jwt.backends.JSONWebTokenBackend',
    'django.contrib.auth.backends.ModelBackend',
]

GRAPHQL_JWT = {
    'JWT_VERIFY_EXPIRATION': True,
    'JWT_LONG_RUNNING_REFRESH_TOKEN': True,
    'JWT_EXPIRATION_DELTA': timedelta(days=7),
    'JWT_REFRESH_EXPIRATION_DELTA': timedelta(days=30),
    'JWT_AUTH_HEADER_PREFIX': 'JWT',
}

# Channels / Redis Configuration
if os.environ.get('REDIS_URL'):
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                "hosts": [{
                    "address": os.environ.get('REDIS_URL'),
                    "socket_timeout": 30,
                    "socket_connect_timeout": 30,
                    "retry_on_timeout": True,
                }],
            },
        },
    }
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }

# GIS Library Paths
# Se definen solo para macOS local. En Linux/Docker, Django autodetecta las librerías instaladas en el sistema.
import sys
if sys.platform == 'darwin':
    GDAL_LIBRARY_PATH = '/opt/homebrew/opt/gdal/lib/libgdal.dylib'
    GEOS_LIBRARY_PATH = '/opt/homebrew/opt/geos/lib/libgeos_c.dylib'

from django.urls import reverse_lazy

# Configuración de django-unfold (Panel Administrativo Premium)
UNFOLD = {
    "SITE_TITLE": "Administración de Clanship",
    "SITE_HEADER": "Clanship",
    "SITE_SYMBOL": "handyman",  # Icono para la marca (Material Symbols)
    "SITE_ICON": {
        "light": lambda request: "/static/app_icon.jpg",
        "dark": lambda request: "/static/app_icon.jpg",
    },
    "SITE_LOGO": {
        "light": lambda request: "/static/app_icon.jpg",
        "dark": lambda request: "/static/app_icon.jpg",
    },
    "THEME": "light",
    "STYLES": [
        lambda request: "/static/css/admin_theme.css",
    ],
    "DASHBOARD_CALLBACK": "core.views.dashboard_callback",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
}

# ─── Configuración de Email (Resend) ─────────────────────────────────────────
# Usamos la API de Resend (https://resend.com) para el envío de correos.
# Configura RESEND_API_KEY en el .env del servidor.
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')

# Dirección remitente verificada en Resend (dominio clanship.cl debe estar verificado)
NO_REPLY_EMAIL_USER = os.environ.get('NO_REPLY_EMAIL_USER', 'noreply@clanship.cl')
NO_REPLY_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL',
    f'Equipo Clanship <{os.environ.get("NO_REPLY_EMAIL_USER", "noreply@clanship.cl")}>',
)
DEFAULT_FROM_EMAIL = NO_REPLY_FROM_EMAIL