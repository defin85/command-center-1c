from django.db import migrations, models


def _forward_fill_exposure_revision(apps, schema_editor):
    OperationExposure = apps.get_model("templates", "OperationExposure")

    for exposure in OperationExposure.objects.select_related("definition").all().iterator():
        definition = getattr(exposure, "definition", None)
        try:
            definition_revision = int(getattr(definition, "contract_version", 1) or 1)
        except (TypeError, ValueError):
            definition_revision = 1
        if definition_revision < 1:
            definition_revision = 1
        if exposure.exposure_revision != definition_revision:
            exposure.exposure_revision = definition_revision
            exposure.save(update_fields=["exposure_revision"])


def _reverse_fill_exposure_revision(apps, schema_editor):
    OperationExposure = apps.get_model("templates", "OperationExposure")
    OperationExposure.objects.all().update(exposure_revision=1)


class Migration(migrations.Migration):
    dependencies = [
        ("templates", "0019_drop_operation_templates_table"),
    ]

    operations = [
        migrations.AddField(
            model_name="operationexposure",
            name="exposure_revision",
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.RunPython(
            _forward_fill_exposure_revision,
            _reverse_fill_exposure_revision,
        ),
    ]
