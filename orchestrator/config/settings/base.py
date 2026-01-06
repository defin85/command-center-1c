"""
Django settings for CommandCenter1C orchestrator.
Base settings shared across all environments.
"""
from pathlib import Path
from datetime import timedelta
import environ
from django.core.exceptions import ImproperlyConfigured

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

ENABLE_DJANGO_PROMETHEUS = env('ENABLE_DJANGO_PROMETHEUS', default='false').lower() == 'true'
DJANGO_PROMETHEUS_ENABLED = False
if ENABLE_DJANGO_PROMETHEUS:
    try:
        import django_prometheus  # noqa: F401
    except Exception:
        DJANGO_PROMETHEUS_ENABLED = False
    else:
        DJANGO_PROMETHEUS_ENABLED = True

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
    # django_celery_beat removed - Go Scheduler handles periodic tasks
    'channels',  # Django Channels for WebSocket support
    'django_json_widget',  # JSON Editor widget for Admin

    # Local apps
    'apps.operations',
    'apps.databases',
    'apps.templates',
    'apps.monitoring',
    'apps.files',  # File storage (Phase 5.1)
    'apps.artifacts',  # Artifact storage (v2)
    'apps.runtime_settings',
    'apps.api_v2',  # API v2 with action-based routing
    'apps.api_internal',  # Internal API for Go Worker
]

if DJANGO_PROMETHEUS_ENABLED:
    INSTALLED_APPS.insert(0, 'django_prometheus')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Serve static files (required for ASGI/Daphne)
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'apps.operations.middleware.PrometheusMetricsMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

if DJANGO_PROMETHEUS_ENABLED:
    MIDDLEWARE.insert(0, 'django_prometheus.middleware.PrometheusBeforeMiddleware')
    MIDDLEWARE.append('django_prometheus.middleware.PrometheusAfterMiddleware')

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
# WhiteNoise storage with compression and caching
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

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
    'ENUM_NAME_OVERRIDES': {
        'DatabaseStatusEnum': ['active', 'inactive', 'error', 'maintenance'],
        'OperationStatusEnum': ['pending', 'running', 'completed', 'failed', 'cancelled'],
    },
    'EXCLUDE_PATHS': [
        r'^/api/v2/internal/.*$',
    ],
    'APPEND_PATHS': {
        '/api/v2/databases/stream/': {
            'get': {
                'operationId': 'v2_databases_stream_retrieve',
                'summary': 'Database SSE stream',
                'description': (
                    'SSE endpoint for database updates. '
                    'Use ticket from /databases/stream-ticket/.'
                ),
                'tags': ['v2'],
                'parameters': [
                    {
                        'name': 'ticket',
                        'in': 'query',
                        'required': True,
                        'schema': {'type': 'string'},
                        'description': 'Short-lived SSE ticket from /databases/stream-ticket/.',
                    },
                ],
                'responses': {
                    '200': {'description': 'SSE stream (text/event-stream)'},
                    '401': {'description': 'Unauthorized'},
                    '403': {'description': 'Forbidden'},
                    '429': {'description': 'Stream already active'},
                },
            },
        },
        '/api/v2/operations/stream/': {
            'get': {
                'operationId': 'v2_operations_stream_retrieve',
                'summary': 'Operation SSE stream',
                'description': (
                    'SSE endpoint for operation updates. '
                    'Prefer ticket from /operations/stream-ticket/. '
                    'Legacy token auth is deprecated.'
                ),
                'tags': ['v2'],
                'parameters': [
                    {
                        'name': 'ticket',
                        'in': 'query',
                        'required': False,
                        'schema': {'type': 'string'},
                        'description': 'Short-lived SSE ticket from /operations/stream-ticket/.',
                    },
                    {
                        'name': 'operation_id',
                        'in': 'query',
                        'required': False,
                        'schema': {'type': 'string'},
                        'description': 'Operation ID (deprecated legacy token auth).',
                    },
                    {
                        'name': 'token',
                        'in': 'query',
                        'required': False,
                        'schema': {'type': 'string'},
                        'description': 'Legacy token auth (deprecated).',
                    },
                ],
                'responses': {
                    '200': {'description': 'SSE stream (text/event-stream)'},
                    '401': {'description': 'Unauthorized'},
                },
            },
        },
        '/api/v2/operations/stream-mux/': {
            'get': {
                'operationId': 'v2_operations_stream_mux_retrieve',
                'summary': 'Operation SSE multiplex stream',
                'description': (
                    'SSE endpoint for multiplex operation updates. '
                    'Use ticket from /operations/stream-mux-ticket/.'
                ),
                'tags': ['v2'],
                'parameters': [
                    {
                        'name': 'ticket',
                        'in': 'query',
                        'required': True,
                        'schema': {'type': 'string'},
                        'description': 'Short-lived SSE ticket from /operations/stream-mux-ticket/.',
                    },
                ],
                'responses': {
                    '200': {'description': 'SSE stream (text/event-stream)'},
                    '401': {'description': 'Unauthorized'},
                    '429': {'description': 'Stream already active'},
                },
            },
        },
    },
}

# Celery Configuration - REMOVED
# Go Worker handles all task execution via Redis queue (cc1c:operations:v1)
# See docs/roadmaps/CELERY_REMOVAL_ROADMAP.md

# Redis
REDIS_HOST = env('REDIS_HOST', default='localhost')
REDIS_PORT = env('REDIS_PORT', default='6379')
REDIS_DB = env('REDIS_DB', default='0')

# ========== Redis Queue Configuration (Message Protocol v2.0) ==========
REDIS_QUEUE_OPERATIONS = "cc1c:operations:v1"
REDIS_QUEUE_RESULTS = "cc1c:operations:results:v1"
REDIS_QUEUE_DLQ = "cc1c:operations:dlq:v1"

# Idempotency & Heartbeat
# REDIS_KEY_ENQUEUE_LOCK - Orchestrator uses this to prevent duplicate enqueue requests
# REDIS_KEY_TASK_LOCK - Worker uses this for processing idempotency (different key!)
REDIS_KEY_ENQUEUE_LOCK = "cc1c:enqueue:{task_id}:lock"
REDIS_KEY_TASK_LOCK = "cc1c:task:{task_id}:lock"
REDIS_KEY_GLOBAL_TARGET_LOCK = "cc1c:global_target:{target_ref}:lock"
REDIS_KEY_TASK_PROGRESS = "cc1c:task:{task_id}:progress"
REDIS_KEY_WORKER_HEARTBEAT = "cc1c:worker:{worker_id}:heartbeat"

# Worker Authentication
WORKER_API_KEY = env('WORKER_API_KEY', default='dev-worker-key-change-in-production')

# DLQ Retention
DLQ_RETENTION_DAYS = 7

# CORS
# Port 8180 - API Gateway outside Windows reserved range (8013-8112)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:8180",
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
# ВАЖНО: Go сервисы ожидают HEX (64+ hex chars = 32+ bytes).
# Должен совпадать между Django Orchestrator и Go Worker!
CREDENTIALS_TRANSPORT_KEY = env(
    'CREDENTIALS_TRANSPORT_KEY',
    default=''  # hex string (64+ chars). For dev it will be auto-generated by bootstrap.
)

if not CREDENTIALS_TRANSPORT_KEY:
    import warnings
    warnings.warn(
        "CREDENTIALS_TRANSPORT_KEY environment variable is not set. "
        "Encrypted credentials transport to Go services will not work. "
        "Generate one with: openssl rand -hex 32",
        RuntimeWarning,
    )
else:
    try:
        _transport_key_bytes = bytes.fromhex(CREDENTIALS_TRANSPORT_KEY)
    except ValueError as e:
        raise ImproperlyConfigured(
            "CREDENTIALS_TRANSPORT_KEY invalid: must be hex-encoded (64+ hex chars = 32+ bytes). "
            "Generate with: openssl rand -hex 32"
        ) from e

    if len(_transport_key_bytes) < 32:
        raise ImproperlyConfigured(
            "CREDENTIALS_TRANSPORT_KEY too short: need 32+ bytes (64+ hex chars). "
            "Generate with: openssl rand -hex 32"
        )

# Installation Service Configuration
# Port 8185 - outside Windows reserved range (8013-8112)
INSTALLATION_SERVICE_URL = env(
    'INSTALLATION_SERVICE_URL',
    default='http://localhost:8185'
)
INSTALLATION_SERVICE_TIMEOUT = int(env(
    'INSTALLATION_SERVICE_TIMEOUT',
    default='180'  # 3 minutes
))

# OData runs inside worker (direct HTTP).

# Worker Configuration
# Port 9091 - Go Worker health endpoint
WORKER_URL = env(
    'WORKER_URL',
    default='http://localhost:9091'
)

# Default RAS Server address (used for new clusters)
# Should match RAS_SERVER_ADDR in Go services and RAS_PORT in start scripts
RAS_DEFAULT_SERVER = env(
    'RAS_SERVER_ADDR',
    default='localhost:1545'
)

# Health Check Settings
HEALTH_CHECK_CLUSTER_INTERVAL = 60  # секунды
HEALTH_CHECK_DATABASE_INTERVAL = 30
HEALTH_CHECK_FAILURE_THRESHOLD = 3  # consecutive failures до ERROR

HEALTH_CHECK_DATABASE_BATCH_SIZE = 20  # батч для Database health checks
HEALTH_CHECK_TIMEOUT = 30  # секунды

# Status History Retention
STATUS_HISTORY_RETENTION_DAYS = 90

# ========== Extension Storage Configuration ==========
EXTENSION_STORAGE_PATH = BASE_DIR.parent / 'storage' / 'extensions'

# ========== IBCMD Storage Configuration ==========
# Backend reserved for future S3 support (local is default).
IBCMD_STORAGE_BACKEND = env('IBCMD_STORAGE_BACKEND', default='local')
IBCMD_STORAGE_PATH = BASE_DIR.parent / 'storage' / 'ibcmd'

# ========== Artifact Storage Configuration (MinIO) ==========
MINIO_ENDPOINT = env('MINIO_ENDPOINT', default='localhost:9000')
MINIO_ACCESS_KEY = env('MINIO_ACCESS_KEY', default='minioadmin')
MINIO_SECRET_KEY = env('MINIO_SECRET_KEY', default='minioadmin')
MINIO_BUCKET = env('MINIO_BUCKET', default='cc1c-artifacts')
MINIO_SECURE = env.bool('MINIO_SECURE', default=False)

# ========== File Upload Configuration (Phase 5.1) ==========
# Base directory for uploaded files
UPLOAD_ROOT = env('UPLOAD_ROOT', default=str(BASE_DIR.parent / 'storage' / 'uploads'))

# Maximum file upload size (100 MB)
FILE_UPLOAD_MAX_SIZE = int(env('FILE_UPLOAD_MAX_SIZE', default=str(100 * 1024 * 1024)))

# Default file expiration (24 hours)
FILE_UPLOAD_EXPIRY_HOURS = int(env('FILE_UPLOAD_EXPIRY_HOURS', default='24'))

# Maximum allowed expiry hours (7 days = 168 hours)
FILE_UPLOAD_MAX_EXPIRY_HOURS = int(env('FILE_UPLOAD_MAX_EXPIRY_HOURS', default='168'))

# ========== System Monitoring Configuration ==========
# Ports outside Windows reserved range (8013-8112)
API_GATEWAY_URL = env('API_GATEWAY_URL', default='http://localhost:8180')
FRONTEND_URL = env('FRONTEND_URL', default='http://localhost:5173')

MONITORED_SERVICES = [
    {
        'name': 'API Gateway',
        'type': 'backend',
        'health_url': f'{API_GATEWAY_URL}/health',
        'critical': True,
    },
    {
        'name': 'frontend',
        'type': 'frontend',
        'health_url': f'{FRONTEND_URL}/',
        'critical': False,
    },
    {
        'name': 'worker',
        'type': 'backend',
        'health_url': f'{WORKER_URL}/health',
        'critical': True,
    },
]

# ========== Go Worker Feature Flags ==========
# Используются для постепенной миграции с Celery на Go Worker
# Каждый флаг позволяет переключать конкретный компонент независимо
ENABLE_GO_SCHEDULER = env.bool('ENABLE_GO_SCHEDULER', default=False)
ENABLE_GO_TEMPLATE_ENGINE = env.bool('ENABLE_GO_TEMPLATE_ENGINE', default=False)
ENABLE_GO_WORKFLOW_ENGINE = env.bool('ENABLE_GO_WORKFLOW_ENGINE', default=False)

# Celery removed - this flag kept for backward compatibility during transition
# Always False now - all operations go through Go Worker via Redis queue
CELERY_ENABLED = env.bool('CELERY_ENABLED', default=False)

# Internal API token для Go Worker
# КРИТИЧНО: Должен совпадать с INTERNAL_API_TOKEN в Go Worker
INTERNAL_API_TOKEN = env('INTERNAL_API_TOKEN', default='dev-internal-token-change-in-production')
