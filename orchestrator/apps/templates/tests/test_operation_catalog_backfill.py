from __future__ import annotations

import pytest

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
def test_backfill_ignores_legacy_ui_action_catalog_payloads():
    OperationTemplate.objects.all().delete()
    OperationDefinition.objects.all().delete()
    OperationExposure.objects.all().delete()
    OperationMigrationIssue.objects.all().delete()

    RuntimeSetting.objects.update_or_create(
        key="ui.action_catalog",
        defaults={
            "value": {
                "catalog_version": 1,
                "extensions": {
                    "actions": [
                        {
                            "id": "extensions.list.legacy",
                            "capability": "extensions.list",
                            "label": "Legacy list",
                            "contexts": ["database_card"],
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
        key="ui.action_catalog",
        defaults={
            "status": TenantRuntimeSettingOverride.STATUS_PUBLISHED,
            "value": {
                "catalog_version": 1,
                "extensions": {
                    "actions": [
                        {
                            "id": "extensions.sync.legacy",
                            "capability": "extensions.sync",
                            "label": "Legacy sync",
                            "contexts": ["bulk_page"],
                            "executor": {"kind": "ibcmd_cli", "driver": "ibcmd", "command_id": "infobase.extension.update"},
                        },
                    ]
                },
            },
        },
    )

    stats = run_unified_operation_catalog_backfill()

    assert stats.actions_processed == 0
    assert stats.issues_created == 0
    assert OperationExposure.objects.filter(surface=OperationExposure.SURFACE_ACTION_CATALOG).count() == 0
