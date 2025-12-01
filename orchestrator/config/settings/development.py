"""Development settings."""
from .base import *

DEBUG = True

ALLOWED_HOSTS = ['*']

# Development-specific apps
INSTALLED_APPS += [
    'django_extensions',
]

# Use PostgreSQL from base.py (configured via .env.local)
# SQLite removed - doesn't support concurrent access from Celery workers

# Отключаем аутентификацию для demo/dev режима (оставляем JWT, но делаем AllowAny)
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    # Оставляем JWT authentication для совместимости с API Gateway
}

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
