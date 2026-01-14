from django.apps import AppConfig


class ArtifactsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.artifacts"
    verbose_name = "Artifacts"

    def ready(self):
        from .signals import register_artifact_usage_signals

        register_artifact_usage_signals()
