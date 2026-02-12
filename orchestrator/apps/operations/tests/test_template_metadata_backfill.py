from __future__ import annotations

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.operations.models import BatchOperation
from apps.templates.models import OperationDefinition, OperationExposure


def _create_template_with_exposure(*, template_id: str) -> tuple[str, OperationExposure]:
    definition = OperationDefinition.objects.create(
        tenant_scope="global",
        executor_kind=OperationDefinition.EXECUTOR_DESIGNER_CLI,
        executor_payload={
            "operation_type": "designer_cli",
            "target_entity": "infobase",
            "template_data": {},
        },
        contract_version=1,
        fingerprint=f"fp-{template_id}",
        status=OperationDefinition.STATUS_ACTIVE,
    )
    exposure = OperationExposure.objects.create(
        definition=definition,
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias=template_id,
        tenant=None,
        label=template_id,
        description="",
        is_active=True,
        capability="",
        contexts=[],
        display_order=0,
        capability_config={},
        status=OperationExposure.STATUS_PUBLISHED,
    )
    return template_id, exposure


def _create_batch_operation(*, operation_id: str, metadata: dict) -> BatchOperation:
    return BatchOperation.objects.create(
        id=operation_id,
        name=f"Operation {operation_id}",
        operation_type=BatchOperation.TYPE_DESIGNER_CLI,
        target_entity="infobase",
        payload={},
        metadata=metadata,
        created_by="pytest",
    )


@pytest.mark.django_db
def test_backfill_operation_template_metadata_fills_alias_and_exposure_id():
    template_id, exposure = _create_template_with_exposure(template_id="tpl-op-meta-1")

    op_missing_exposure_id = _create_batch_operation(
        operation_id="op-meta-missing-exp-id",
        metadata={"workflow_execution_id": "wf-1", "template_id": template_id},
    )
    op_stale_exposure_id = _create_batch_operation(
        operation_id="op-meta-only",
        metadata={"template_id": template_id, "template_exposure_id": "stale"},
    )

    out = StringIO()
    call_command("backfill_operation_template_metadata", "--json", stdout=out)
    payload = json.loads(out.getvalue())

    assert payload["scanned_operations"] == 2
    assert payload["operations_with_template_ref"] == 2
    assert payload["updated_operations"] == 2
    assert payload["missing_exposure"] == 0
    assert payload["source_template_fk"] == 0
    assert payload["source_metadata_template_id"] == 2

    op_missing_exposure_id.refresh_from_db()
    assert op_missing_exposure_id.metadata["template_id"] == template_id
    assert op_missing_exposure_id.metadata["template_exposure_id"] == str(exposure.id)

    op_stale_exposure_id.refresh_from_db()
    assert op_stale_exposure_id.metadata["template_id"] == template_id
    assert op_stale_exposure_id.metadata["template_exposure_id"] == str(exposure.id)


@pytest.mark.django_db
def test_backfill_operation_template_metadata_strict_fails_and_rolls_back():
    template_id = "tpl-op-meta-missing"
    operation = _create_batch_operation(
        operation_id="op-meta-missing",
        metadata={"template_id": template_id},
    )

    with pytest.raises(CommandError):
        call_command("backfill_operation_template_metadata", "--strict")

    operation.refresh_from_db()
    assert operation.metadata == {"template_id": template_id}


@pytest.mark.django_db
def test_backfill_operation_template_metadata_dry_run_rolls_back():
    template_id, exposure = _create_template_with_exposure(template_id="tpl-op-meta-dry")
    operation = _create_batch_operation(
        operation_id="op-meta-dry",
        metadata={"template_id": template_id},
    )

    call_command("backfill_operation_template_metadata", "--dry-run")

    operation.refresh_from_db()
    assert operation.metadata == {"template_id": template_id}
    assert str(exposure.id) != operation.metadata.get("template_exposure_id")
