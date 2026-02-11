from __future__ import annotations

import json
from io import StringIO

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.templates.models import (
    OperationDefinition,
    OperationExposure,
    OperationExposureGroupPermission,
    OperationExposurePermission,
    OperationTemplate,
    OperationTemplateGroupPermission,
    OperationTemplatePermission,
)


def _create_template_with_exposure(*, template_id: str) -> OperationTemplate:
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
    OperationExposure.objects.create(
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
    return template


@pytest.mark.django_db
def test_backfill_operation_exposure_permissions_persists_and_has_zero_parity(django_user_model):
    template = _create_template_with_exposure(template_id="tpl-oep-backfill")
    user = django_user_model.objects.create_user(username="legacy_u", password="pass")
    group = Group.objects.create(name="legacy_group")

    OperationTemplatePermission.objects.create(user=user, template=template, level=10, notes="u-note")
    OperationTemplateGroupPermission.objects.create(group=group, template=template, level=30, notes="g-note")

    out = StringIO()
    call_command("backfill_operation_exposure_permissions", "--json", stdout=out)
    payload = json.loads(out.getvalue())

    assert payload["direct_backfilled_created"] == 1
    assert payload["group_backfilled_created"] == 1
    assert payload["parity_mismatches_total"] == 0
    assert payload["direct_missing_exposure"] == 0
    assert payload["group_missing_exposure"] == 0

    assert OperationExposurePermission.objects.count() == 1
    assert OperationExposureGroupPermission.objects.count() == 1

    strict_out = StringIO()
    call_command("backfill_operation_exposure_permissions", "--strict-parity", "--json", stdout=strict_out)
    strict_payload = json.loads(strict_out.getvalue())
    assert strict_payload["parity_mismatches_total"] == 0


@pytest.mark.django_db
def test_backfill_operation_exposure_permissions_strict_fails_when_exposure_missing(django_user_model):
    template = OperationTemplate.objects.create(
        id="tpl-missing-exp",
        name="Template missing exposure",
        description="",
        operation_type="designer_cli",
        target_entity="infobase",
        template_data={},
        is_active=True,
    )
    user = django_user_model.objects.create_user(username="legacy_u_2", password="pass")
    OperationTemplatePermission.objects.create(user=user, template=template, level=10, notes="")

    with pytest.raises(CommandError):
        call_command("backfill_operation_exposure_permissions", "--strict-parity")

