from django.apps import AppConfig


class ApiInternalConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.api_internal'
    verbose_name = 'Internal API'
