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

# Read .env files with priority: .env.local > .env
# .env.local для локальной разработки (gitignored, содержит secrets)
# .env для production/CI (checked in, содержит defaults)
env_file_local = BASE_DIR.parent / '.env.local'
env_file = BASE_DIR.parent / '.env'

if env_file_local.exists():
    environ.Env.read_env(str(env_file_local))
elif env_file.exists():
    environ.Env.read_env(str(env_file))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('DJANGO_SECRET_KEY', default='django-insecure-change-me-in-production')

# Application definition
INSTALLED_APPS = [
    # ASGI server - MUST be before django.contrib.staticfiles
    'daphne',

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
    'channels',  # Django Channels for WebSocket support

    # Local apps
    'apps.operations',
    'apps.databases',
    'apps.templates',
    'apps.monitoring',
    'apps.api_v2',  # API v2 with action-based routing
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

# Django Channels - Channel Layer Configuration
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(env('REDIS_HOST', default='localhost'), int(env('REDIS_PORT', default='6379')))],
            "prefix": "cc1c:ws",
            # Increase capacity for high traffic
            "capacity": 1500,
            "expiry": 60,
        },
    },
}

# For testing - In-memory channel layer
if env('TESTING', default='false').lower() == 'true':
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer"
        }
    }

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
        'apps.core.authentication.ServiceJWTAuthentication',  # Supports service tokens
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

# Simple JWT settings
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),  # Для dev - 24 часа, для prod уменьшить
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': env('JWT_SECRET', default='your-jwt-secret-change-in-production'),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
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

# ========== Redis Queue Configuration (Message Protocol v2.0) ==========
REDIS_QUEUE_OPERATIONS = "cc1c:operations:v1"
REDIS_QUEUE_RESULTS = "cc1c:operations:results:v1"
REDIS_QUEUE_DLQ = "cc1c:operations:dlq:v1"

# Idempotency & Heartbeat
REDIS_KEY_TASK_LOCK = "cc1c:task:{task_id}:lock"
REDIS_KEY_TASK_PROGRESS = "cc1c:task:{task_id}:progress"
REDIS_KEY_WORKER_HEARTBEAT = "cc1c:worker:{worker_id}:heartbeat"

# Worker Authentication
WORKER_API_KEY = env('WORKER_API_KEY', default='dev-worker-key-change-in-production')

# DLQ Retention
DLQ_RETENTION_DAYS = 7

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
    # Использовать fallback ключ для development (valid Fernet key)
    FIELD_ENCRYPTION_KEY = 'MqYe7fA3_doV3nD15UAtPUb6Aq0_cgVg6kfdwjDlpCo='

# Credentials Transport Encryption (AES-GCM-256)
# ВАЖНО: Должен быть 32+ bytes для AES-256!
# Должен совпадать между Django Orchestrator и Go Worker!
CREDENTIALS_TRANSPORT_KEY = env(
    'CREDENTIALS_TRANSPORT_KEY',
    default='dev-transport-key-change-in-prod-32bytes-minimum'  # 32+ символов для AES-256
)

if len(CREDENTIALS_TRANSPORT_KEY.encode('utf-8')) < 32:
    import warnings
    warnings.warn(
        "CREDENTIALS_TRANSPORT_KEY is too short (should be 32+ bytes). "
        "Add to .env.local: CREDENTIALS_TRANSPORT_KEY=<strong-32+-byte-key>",
        RuntimeWarning
    )

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

# ========== Extension Storage Configuration ==========
EXTENSION_STORAGE_PATH = BASE_DIR.parent / 'storage' / 'extensions'

# ========== System Monitoring Configuration ==========
MONITORED_SERVICES = [
    {
        'name': 'API Gateway',
        'type': 'backend',
        'health_url': 'http://localhost:8080/health',
        'critical': True,
    },
    {
        'name': 'ras-adapter',
        'type': 'backend',
        'health_url': 'http://localhost:8088/health',
        'critical': True,
    },
    {
        'name': 'batch-service',
        'type': 'backend',
        'health_url': 'http://localhost:8087/health',
        'critical': False,
    },
]
