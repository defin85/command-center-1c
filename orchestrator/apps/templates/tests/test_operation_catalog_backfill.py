from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.runtime_settings.action_catalog import UI_ACTION_CATALOG_KEY
from apps.runtime_settings.models import RuntimeSetting, TenantRuntimeSettingOverride
from apps.templates.models import (
    OperationDefinition,
    OperationExposure,
    OperationMigrationIssue,
    OperationTemplate,
)
from apps.templates.operation_catalog_backfill import run_unified_operation_catalog_backfill
from apps.tenancy.models import Tenant


@pytest.mark.django_db
def test_backfill_templates_creates_unified_definition_and_exposure():
    OperationTemplate.objects.all().delete()
    OperationDefinition.objects.all().delete()
    OperationExposure.objects.all().delete()
    OperationMigrationIssue.objects.all().delete()

    template = OperationTemplate.objects.create(
        id="tpl-unified-1",
        name="Unified Template",
        description="test",
        operation_type="ibcmd_cli",
        target_entity="infobase",
        template_data={"command_id": "infobase.extension.list"},
        is_active=True,
    )

    stats = run_unified_operation_catalog_backfill()

    assert stats.templates_processed == 1
    exposure = OperationExposure.objects.get(surface=OperationExposure.SURFACE_TEMPLATE, alias=template.id)
    assert exposure.status == OperationExposure.STATUS_PUBLISHED
    assert exposure.definition.executor_kind == OperationDefinition.EXECUTOR_IBCMD_CLI
    assert exposure.definition.tenant_scope == "global"


@pytest.mark.django_db
def test_backfill_action_catalog_deduplicates_definitions_per_scope():
    OperationTemplate.objects.all().delete()
    OperationDefinition.objects.all().delete()
    OperationExposure.objects.all().delete()
    OperationMigrationIssue.objects.all().delete()

    RuntimeSetting.objects.update_or_create(
        key=UI_ACTION_CATALOG_KEY,
        defaults={
            "value": {
                "catalog_version": 1,
                "extensions": {
                    "actions": [
                        {
                            "id": "extensions.list.1",
                            "capability": "extensions.list",
                            "label": "List 1",
                            "contexts": ["database_card"],
                            "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": "infobase.extension.list"},
                        },
                        {
                            "id": "extensions.list.2",
                            "capability": "extensions.list",
                            "label": "List 2",
                            "contexts": ["bulk_page"],
                            "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": "infobase.extension.list"},
                        },
                    ]
                },
            }
        },
    )

    tenant = Tenant.objects.create(slug="tenant-backfill", name="Tenant Backfill")
    TenantRuntimeSettingOverride.objects.update_or_create(
        tenant=tenant,
        key=UI_ACTION_CATALOG_KEY,
        defaults={
            "status": TenantRuntimeSettingOverride.STATUS_PUBLISHED,
            "value": {
                "catalog_version": 1,
                "extensions": {
                    "actions": [
                        {
                            "id": "extensions.list.tenant",
                            "capability": "extensions.list",
                            "label": "Tenant List",
                            "contexts": ["database_card"],
                            "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": "infobase.extension.list"},
                        },
                    ]
                },
            },
        },
    )

    stats = run_unified_operation_catalog_backfill()

    assert stats.actions_processed == 3
    assert OperationExposure.objects.filter(surface=OperationExposure.SURFACE_ACTION_CATALOG).count() == 3
    # Global actions share one definition; tenant override keeps isolated scope definition.
    assert OperationDefinition.objects.filter(tenant_scope="global").count() == 1
    assert OperationDefinition.objects.filter(tenant_scope=f"tenant:{tenant.id}").count() == 1


@pytest.mark.django_db
def test_backfill_set_flags_invalid_binding_marked_invalid(monkeypatch):
    OperationTemplate.objects.all().delete()
    OperationDefinition.objects.all().delete()
    OperationExposure.objects.all().delete()
    OperationMigrationIssue.objects.all().delete()

    RuntimeSetting.objects.update_or_create(
        key=UI_ACTION_CATALOG_KEY,
        defaults={
            "value": {
                "catalog_version": 1,
                "extensions": {
                    "actions": [
                        {
                            "id": "extensions.set_flags.bad",
                            "capability": "extensions.set_flags",
                            "label": "Set flags bad",
                            "contexts": ["database_card"],
                            "executor": {
                                "kind": "ibcmd_cli",
                                "driver": "ibcmd",
                                "command_id": "infobase.extension.update",
                            },
                        },
                    ]
                },
            }
        },
    )

    monkeypatch.setattr(
        "apps.templates.operation_catalog_backfill.resolve_driver_catalog_versions",
        lambda _driver: SimpleNamespace(base_version=1, overrides_version=1),
    )
    monkeypatch.setattr(
        "apps.templates.operation_catalog_backfill.get_effective_driver_catalog",
        lambda **_kwargs: SimpleNamespace(
            catalog={
                "commands_by_id": {
                    "infobase.extension.update": {
                        "params_by_name": {
                            "name": {"type": "string"},
                        }
                    }
                }
            }
        ),
    )

    run_unified_operation_catalog_backfill()

    exposure = OperationExposure.objects.get(alias="extensions.set_flags.bad")
    assert exposure.status == OperationExposure.STATUS_INVALID
    issue = OperationMigrationIssue.objects.get(exposure=exposure)
    assert issue.code == "INVALID_SET_FLAGS_TARGET_BINDING"
