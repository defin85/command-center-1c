"""
Django settings for CommandCenter1C orchestrator.
Base settings shared across all environments.
"""
import os
from pathlib import Path
import environ

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Initialize environment variables
env = environ.Env(
    DEBUG=(bool, False)
)

# Read .env file if exists
env_file = BASE_DIR.parent / '.env'
if env_file.exists():
    environ.Env.read_env(str(env_file))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('DJANGO_SECRET_KEY', default='django-insecure-change-me-in-production')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party apps
    'rest_framework',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'django_celery_beat',  # Database-backed periodic tasks

    # Local apps
    'apps.operations',
    'apps.databases',
    'apps.templates',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME', default='commandcenter'),
        'USER': env('DB_USER', default='commandcenter'),
        'PASSWORD': env('DB_PASSWORD', default='password'),
        'HOST': env('DB_HOST', default='localhost'),
        'PORT': env('DB_PORT', default='5432'),
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# Spectacular settings (OpenAPI/Swagger)
SPECTACULAR_SETTINGS = {
    'TITLE': 'CommandCenter1C API',
    'DESCRIPTION': 'API для управления операциями в 700+ базах 1С',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# Celery Configuration
CELERY_BROKER_URL = env('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env('REDIS_URL', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes

# Redis
REDIS_HOST = env('REDIS_HOST', default='localhost')
REDIS_PORT = env('REDIS_PORT', default='6379')
REDIS_DB = env('REDIS_DB', default='0')

# CORS
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:8080",
]
CORS_ALLOW_CREDENTIALS = True

# Encryption key for django-encrypted-model-fields
FIELD_ENCRYPTION_KEY = env('DB_ENCRYPTION_KEY', default=None)

if not FIELD_ENCRYPTION_KEY:
    import warnings
    warnings.warn(
        "DB_ENCRYPTION_KEY environment variable is not set. "
        "Sensitive data will not be encrypted. "
        "Generate one with: python scripts/generate_encryption_key.py",
        RuntimeWarning
    )
    # Использовать fallback ключ для development
    FIELD_ENCRYPTION_KEY = 'development-only-insecure-key-32chars!!'

# Installation Service Configuration
INSTALLATION_SERVICE_URL = env(
    'INSTALLATION_SERVICE_URL',
    default='http://localhost:8085'
)
INSTALLATION_SERVICE_TIMEOUT = int(env(
    'INSTALLATION_SERVICE_TIMEOUT',
    default='180'  # 3 minutes
))

# Batch Service Configuration
BATCH_SERVICE_URL = env(
    'BATCH_SERVICE_URL',
    default='http://localhost:8087'
)
BATCH_SERVICE_TIMEOUT = int(env(
    'BATCH_SERVICE_TIMEOUT',
    default='60'  # 1 minute
))

# Health Check Settings
HEALTH_CHECK_CLUSTER_INTERVAL = 60  # секунды
HEALTH_CHECK_DATABASE_INTERVAL = 30
HEALTH_CHECK_BATCH_SERVICE_INTERVAL = 30

HEALTH_CHECK_FAILURE_THRESHOLD = 3  # consecutive failures до ERROR
HEALTH_CHECK_BATCH_SERVICE_THRESHOLD = 5  # для BatchService

HEALTH_CHECK_DATABASE_BATCH_SIZE = 20  # батч для Database health checks
HEALTH_CHECK_TIMEOUT = 30  # секунды

# Status History Retention
STATUS_HISTORY_RETENTION_DAYS = 90
