from django.apps import AppConfig


class OperationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.operations'
    verbose_name = 'Operations'

    def ready(self):
        """Import signals when Django starts."""
        import apps.operations.signals  # noqa
