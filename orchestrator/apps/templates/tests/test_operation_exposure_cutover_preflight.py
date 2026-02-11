from __future__ import annotations

import json
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.templates.models import (
    OperationDefinition,
    OperationExposure,
    OperationExposurePermission,
)


def _reset_state() -> None:
    OperationExposurePermission.objects.all().delete()
    OperationExposure.objects.all().delete()
    OperationDefinition.objects.all().delete()


def _create_template_exposure(*, template_id: str) -> OperationExposure:
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
    return OperationExposure.objects.create(
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


def _create_invalid_template_exposure(*, template_id: str) -> OperationExposure:
    definition = OperationDefinition.objects.create(
        tenant_scope="global",
        executor_kind=OperationDefinition.EXECUTOR_DESIGNER_CLI,
        executor_payload={
            "operation_type": "designer_cli",
            "target_entity": "infobase",
            "template_data": "invalid",
        },
        contract_version=1,
        fingerprint=f"fp-invalid-{template_id}",
        status=OperationDefinition.STATUS_ACTIVE,
    )
    return OperationExposure.objects.create(
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


@pytest.mark.django_db
def test_preflight_cutover_command_passes_in_strict_mode_when_ready():
    _reset_state()
    exposure = _create_template_exposure(template_id="tpl-cutover-ready")

    User = get_user_model()
    user = User.objects.create_user(username="preflight_u", password="pass")
    OperationExposurePermission.objects.create(user=user, exposure=exposure, level=10, notes="")

    out = StringIO()
    call_command("preflight_operation_exposure_cutover", "--json", "--strict", stdout=out)
    payload = json.loads(out.getvalue())

    assert payload["summary"]["total_critical_mismatches"] == 0
    by_key = {item["key"]: item for item in payload["checks"]}
    assert by_key["template_exposure_payload_contract"]["mismatches"] == 0
    assert by_key["direct_permission_targets_template_exposure"]["mismatches"] == 0


@pytest.mark.django_db
def test_preflight_cutover_command_strict_fails_on_critical_mismatch():
    _reset_state()
    _create_invalid_template_exposure(template_id="tpl-cutover-mismatch")

    with pytest.raises(CommandError):
        call_command("preflight_operation_exposure_cutover", "--strict")
