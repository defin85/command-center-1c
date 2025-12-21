from django.apps import AppConfig


class TemplatesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.templates'
    verbose_name = 'Operation Templates'

    def ready(self):
        """Register all operation types when app loads."""
        # Import backends to trigger registration
        from apps.templates.workflow.handlers.backends.ibcmd import IBCMDBackend
        from apps.templates.workflow.handlers.backends.ras import RASBackend
        from apps.templates.workflow.handlers.backends.odata import ODataBackend

        # Register operations in the global registry
        RASBackend.register_operations()
        ODataBackend.register_operations()
        IBCMDBackend.register_operations()
