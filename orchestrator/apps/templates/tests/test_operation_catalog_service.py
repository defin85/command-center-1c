from __future__ import annotations

import pytest

from apps.templates.operation_catalog_service import (
    normalize_executor_payload,
    resolve_exposure,
    resolve_definition,
    validate_exposure_payload,
)
from apps.templates.models import OperationExposure


def test_normalize_executor_payload_sets_canonical_driver():
    kind, payload, errors = normalize_executor_payload(
        executor_kind="designer_cli",
        executor_payload={"kind": "designer_cli", "command_id": "cluster.list"},
    )

    assert errors == []
    assert kind == "designer_cli"
    assert payload["kind"] == "designer_cli"
    assert payload["driver"] == "cli"


def test_normalize_executor_payload_fails_closed_on_driver_mismatch():
    _kind, _payload, errors = normalize_executor_payload(
        executor_kind="ibcmd_cli",
        executor_payload={"kind": "ibcmd_cli", "driver": "cli", "command_id": "infobase.extension.list"},
    )

    assert errors
    assert any(item["code"] == "DRIVER_KIND_MISMATCH" for item in errors)


def test_validate_exposure_payload_requires_template_runtime_contract_fields():
    errors = validate_exposure_payload(
        executor_kind="designer_cli",
        definition_payload={"template_data": "invalid"},
        capability="",
        capability_config={},
    )

    codes = {item["code"] for item in errors}
    assert "REQUIRED" in codes
    assert "INVALID_TYPE" in codes


def test_validate_exposure_payload_rejects_unknown_operation_type():
    errors = validate_exposure_payload(
        executor_kind="designer_cli",
        definition_payload={
            "operation_type": "totally_unknown_op",
            "target_entity": "infobase",
            "template_data": {},
        },
        capability="",
        capability_config={},
    )

    assert any(item["code"] == "UNSUPPORTED_OPERATION_TYPE" for item in errors)


@pytest.mark.django_db
def test_resolve_definition_dedup_is_stable_without_redundant_driver():
    first, _ = resolve_definition(
        tenant_scope="global",
        executor_kind="ibcmd_cli",
        executor_payload={
            "kind": "ibcmd_cli",
            "driver": "ibcmd",
            "command_id": "infobase.extension.list",
            "params": {},
        },
        contract_version=1,
    )
    second, _ = resolve_definition(
        tenant_scope="global",
        executor_kind="ibcmd_cli",
        executor_payload={
            "kind": "ibcmd_cli",
            "command_id": "infobase.extension.list",
            "params": {},
        },
        contract_version=1,
    )

    assert first.id == second.id


@pytest.mark.django_db
def test_resolve_exposure_initial_revision_uses_definition_contract_version():
    definition, _ = resolve_definition(
        tenant_scope="global",
        executor_kind="designer_cli",
        executor_payload={
            "kind": "designer_cli",
            "driver": "cli",
            "command_id": "infobase.extension.list",
            "operation_type": "designer_cli",
            "target_entity": "infobase",
            "template_data": {},
        },
        contract_version=3,
    )

    exposure, created = resolve_exposure(
        definition=definition,
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias="tpl-revision-initial",
        tenant_id=None,
        label="Template revision initial",
        description="",
        is_active=True,
        capability="templates.designer_cli",
        contexts=[],
        display_order=0,
        capability_config={},
        status=OperationExposure.STATUS_PUBLISHED,
    )

    assert created is True
    assert exposure.exposure_revision == 3


@pytest.mark.django_db
def test_resolve_exposure_increments_revision_when_definition_changes():
    definition_v1, _ = resolve_definition(
        tenant_scope="global",
        executor_kind="designer_cli",
        executor_payload={
            "kind": "designer_cli",
            "driver": "cli",
            "command_id": "infobase.extension.list",
            "operation_type": "designer_cli",
            "target_entity": "infobase",
            "template_data": {"command_id": "infobase.extension.list"},
        },
        contract_version=1,
    )
    exposure_v1, created_v1 = resolve_exposure(
        definition=definition_v1,
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias="tpl-revision-bump",
        tenant_id=None,
        label="Template revision bump",
        description="",
        is_active=True,
        capability="templates.designer_cli",
        contexts=[],
        display_order=0,
        capability_config={},
        status=OperationExposure.STATUS_PUBLISHED,
    )
    assert created_v1 is True
    assert exposure_v1.exposure_revision == 1

    definition_v2, _ = resolve_definition(
        tenant_scope="global",
        executor_kind="designer_cli",
        executor_payload={
            "kind": "designer_cli",
            "driver": "cli",
            "command_id": "infobase.extension.info",
            "operation_type": "designer_cli",
            "target_entity": "infobase",
            "template_data": {"command_id": "infobase.extension.info"},
        },
        contract_version=1,
    )
    exposure_v2, created_v2 = resolve_exposure(
        definition=definition_v2,
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias="tpl-revision-bump",
        tenant_id=None,
        label="Template revision bump renamed",
        description="updated",
        is_active=True,
        capability="templates.designer_cli",
        contexts=[],
        display_order=0,
        capability_config={},
        status=OperationExposure.STATUS_PUBLISHED,
    )
    assert created_v2 is False
    assert exposure_v2.exposure_revision == 2

    exposure_same_definition, _ = resolve_exposure(
        definition=definition_v2,
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias="tpl-revision-bump",
        tenant_id=None,
        label="Template revision bump renamed again",
        description="updated-again",
        is_active=True,
        capability="templates.designer_cli",
        contexts=[],
        display_order=0,
        capability_config={},
        status=OperationExposure.STATUS_PUBLISHED,
    )
    assert exposure_same_definition.exposure_revision == 2
