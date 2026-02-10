from __future__ import annotations

from typing import Any

from django.db import migrations, models


LEGACY_SURFACE = "action_catalog"
_DEFINITION_ID_KEYS = {
    "definition_id",
    "operation_definition_id",
    "definitionId",
    "operationDefinitionId",
}


def _collect_definition_ids(value: Any, out: set[str]) -> None:
    if isinstance(value, dict):
        for raw_key, nested in value.items():
            key = str(raw_key or "")
            if key in _DEFINITION_ID_KEYS and isinstance(nested, str) and nested.strip():
                out.add(nested.strip())
            _collect_definition_ids(nested, out)
        return
    if isinstance(value, list):
        for item in value:
            _collect_definition_ids(item, out)


def _collect_historical_definition_refs(apps) -> set[str]:
    BatchOperation = apps.get_model("operations", "BatchOperation")
    ExtensionsPlan = apps.get_model("operations", "ExtensionsPlan")
    CommandResultSnapshot = apps.get_model("operations", "CommandResultSnapshot")

    refs: set[str] = set()

    for row in BatchOperation.objects.only("metadata", "payload").iterator():
        _collect_definition_ids(getattr(row, "metadata", None), refs)
        _collect_definition_ids(getattr(row, "payload", None), refs)

    for row in ExtensionsPlan.objects.only("executor", "preconditions").iterator():
        _collect_definition_ids(getattr(row, "executor", None), refs)
        _collect_definition_ids(getattr(row, "preconditions", None), refs)

    for row in CommandResultSnapshot.objects.only("raw_payload", "normalized_payload", "canonical_payload").iterator():
        _collect_definition_ids(getattr(row, "raw_payload", None), refs)
        _collect_definition_ids(getattr(row, "normalized_payload", None), refs)
        _collect_definition_ids(getattr(row, "canonical_payload", None), refs)

    return refs


def remove_action_catalog_exposures_and_cleanup_orphans(apps, schema_editor):
    OperationExposure = apps.get_model("templates", "OperationExposure")
    OperationDefinition = apps.get_model("templates", "OperationDefinition")

    legacy_definition_ids = {
        str(definition_id)
        for definition_id in OperationExposure.objects.filter(surface=LEGACY_SURFACE).values_list("definition_id", flat=True)
    }

    OperationExposure.objects.filter(surface=LEGACY_SURFACE).delete()

    if not legacy_definition_ids:
        return

    historical_refs = _collect_historical_definition_refs(apps)

    for definition in OperationDefinition.objects.filter(id__in=legacy_definition_ids).iterator():
        if OperationExposure.objects.filter(definition_id=definition.id).exists():
            continue
        if str(definition.id) in historical_refs:
            continue
        definition.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("operations", "0032_rename_command_res_tenant__40e42e_idx_command_res_tenant__2b6f75_idx_and_more"),
        ("templates", "0014_canonicalize_definition_executor_driver"),
    ]

    operations = [
        migrations.AlterField(
            model_name="operationexposure",
            name="surface",
            field=models.CharField(choices=[("template", "Template")], max_length=32),
        ),
        migrations.RunPython(remove_action_catalog_exposures_and_cleanup_orphans, migrations.RunPython.noop),
    ]
