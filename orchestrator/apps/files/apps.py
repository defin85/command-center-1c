"""
Django app configuration for files.
"""

from django.apps import AppConfig


class FilesConfig(AppConfig):
    """Configuration for files app."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.files'
    verbose_name = 'File Storage'

    def ready(self):
        """Initialize app when Django starts."""
        pass
