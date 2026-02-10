from __future__ import annotations

import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.templates.models import OperationDefinition, OperationExposure, OperationMigrationIssue
from apps.templates.operation_catalog_service import list_set_flags_apply_mask_preset_findings


def _base_set_flags_definition_payload() -> dict:
    return {
        "kind": "ibcmd_cli",
        "driver": "ibcmd",
        "command_id": "infobase.extension.update",
        "params": {
            "extension_name": "$extension_name",
            "active": "$flags.active",
            "safe_mode": "$flags.safe_mode",
            "unsafe_action_protection": "$flags.unsafe_action_protection",
        },
    }


def _create_set_flags_exposure(
    *,
    alias: str,
    definition_fixed_apply_mask: bool = False,
    capability_config: dict | None = None,
    status: str = OperationExposure.STATUS_PUBLISHED,
) -> OperationExposure:
    payload = _base_set_flags_definition_payload()
    if definition_fixed_apply_mask:
        payload["fixed"] = {
            "apply_mask": {
                "active": True,
                "safe_mode": False,
                "unsafe_action_protection": False,
            }
        }
    definition = OperationDefinition.objects.create(
        tenant_scope="global",
        executor_kind=OperationDefinition.EXECUTOR_IBCMD_CLI,
        executor_payload=payload,
        contract_version=1,
        fingerprint=f"fp-{alias}",
        status=OperationDefinition.STATUS_ACTIVE,
    )
    return OperationExposure.objects.create(
        definition=definition,
        surface=OperationExposure.SURFACE_ACTION_CATALOG,
        alias=alias,
        tenant=None,
        label=alias,
        description="",
        is_active=True,
        capability="extensions.set_flags",
        contexts=["bulk_page"],
        display_order=1,
        capability_config=capability_config
        if capability_config is not None
        else {"target_binding": {"extension_name_param": "extension_name"}},
        status=status,
    )


@pytest.mark.django_db
def test_list_set_flags_apply_mask_preset_findings_detects_all_preset_paths():
    OperationExposure.objects.all().delete()
    OperationDefinition.objects.all().delete()

    _create_set_flags_exposure(alias="set_flags.clean")
    _create_set_flags_exposure(alias="set_flags.def_fixed", definition_fixed_apply_mask=True)
    _create_set_flags_exposure(
        alias="set_flags.cap_cfg",
        capability_config={
            "target_binding": {"extension_name_param": "extension_name"},
            "apply_mask": {
                "active": True,
                "safe_mode": False,
                "unsafe_action_protection": False,
            },
        },
    )
    _create_set_flags_exposure(
        alias="set_flags.cap_fixed",
        capability_config={
            "target_binding": {"extension_name_param": "extension_name"},
            "fixed": {
                "apply_mask": {
                    "active": True,
                    "safe_mode": False,
                    "unsafe_action_protection": False,
                }
            },
        },
    )

    findings = list_set_flags_apply_mask_preset_findings(statuses=[OperationExposure.STATUS_PUBLISHED])
    aliases = {item["alias"] for item in findings}
    assert aliases == {"set_flags.def_fixed", "set_flags.cap_cfg", "set_flags.cap_fixed"}


@pytest.mark.django_db
def test_report_set_flags_apply_mask_presets_command_json_and_write_issues():
    OperationExposure.objects.all().delete()
    OperationDefinition.objects.all().delete()
    OperationMigrationIssue.objects.all().delete()

    exposure = _create_set_flags_exposure(alias="set_flags.report", definition_fixed_apply_mask=True)

    out = StringIO()
    call_command("report_set_flags_apply_mask_presets", "--json", stdout=out)
    payload = json.loads(out.getvalue())
    assert payload["count"] == 1
    assert payload["findings"][0]["alias"] == "set_flags.report"

    call_command("report_set_flags_apply_mask_presets", "--write-issues")
    issues = OperationMigrationIssue.objects.filter(code="SET_FLAGS_APPLY_MASK_PRESET", source_id=str(exposure.id))
    assert issues.count() == 1

    with pytest.raises(CommandError):
        call_command("report_set_flags_apply_mask_presets", "--fail-on-findings")
