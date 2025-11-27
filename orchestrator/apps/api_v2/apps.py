"""Django app configuration for API v2."""

from django.apps import AppConfig


class ApiV2Config(AppConfig):
    """Configuration for API v2 app."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.api_v2'
    verbose_name = 'API v2'
