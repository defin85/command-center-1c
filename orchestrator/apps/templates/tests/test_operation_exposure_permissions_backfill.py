from __future__ import annotations

import json
from io import StringIO

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command

from apps.templates.models import (
    OperationDefinition,
    OperationExposure,
    OperationExposureGroupPermission,
    OperationExposurePermission,
    OperationTemplate,
)


def _create_template_with_exposure(*, template_id: str) -> tuple[OperationTemplate, OperationExposure]:
    template = OperationTemplate.objects.create(
        id=template_id,
        name=f"Template {template_id}",
        description="",
        operation_type="designer_cli",
        target_entity="infobase",
        template_data={},
        is_active=True,
    )
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
    return template, exposure


@pytest.mark.django_db
def test_backfill_operation_exposure_permissions_reports_template_scope_rows(django_user_model):
    _, exposure = _create_template_with_exposure(template_id="tpl-oep-backfill")
    user = django_user_model.objects.create_user(username="legacy_u", password="pass")
    group = Group.objects.create(name="legacy_group")

    OperationExposurePermission.objects.create(user=user, exposure=exposure, level=10, notes="u-note")
    OperationExposureGroupPermission.objects.create(group=group, exposure=exposure, level=30, notes="g-note")

    out = StringIO()
    call_command("backfill_operation_exposure_permissions", "--json", stdout=out)
    payload = json.loads(out.getvalue())

    assert payload["direct_legacy_rows"] == 1
    assert payload["group_legacy_rows"] == 1
    assert payload["direct_backfilled_created"] == 0
    assert payload["group_backfilled_created"] == 0
    assert payload["parity_mismatches_total"] == 0
    assert payload["direct_missing_exposure"] == 0
    assert payload["group_missing_exposure"] == 0

    strict_out = StringIO()
    call_command("backfill_operation_exposure_permissions", "--strict-parity", "--json", stdout=strict_out)
    strict_payload = json.loads(strict_out.getvalue())
    assert strict_payload["parity_mismatches_total"] == 0


@pytest.mark.django_db
def test_backfill_operation_exposure_permissions_strict_parity_passes_on_empty_state():
    out = StringIO()
    call_command("backfill_operation_exposure_permissions", "--strict-parity", "--json", stdout=out)
    payload = json.loads(out.getvalue())
    assert payload["direct_legacy_rows"] == 0
    assert payload["group_legacy_rows"] == 0
    assert payload["parity_mismatches_total"] == 0
