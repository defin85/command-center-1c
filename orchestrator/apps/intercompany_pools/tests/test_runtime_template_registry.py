from __future__ import annotations

import pytest

from apps.intercompany_pools.runtime_template_registry import (
    get_pool_runtime_template_aliases,
    sync_pool_runtime_template_registry,
)
from apps.templates.models import OperationDefinition, OperationExposure


@pytest.mark.django_db
def test_sync_pool_runtime_template_registry_creates_required_aliases() -> None:
    result = sync_pool_runtime_template_registry()

    expected_aliases = set(get_pool_runtime_template_aliases())
    assert "pool.master_data_sync.inbound" in expected_aliases
    assert "pool.master_data_sync.dispatch" in expected_aliases
    assert "pool.master_data_sync.finalize" in expected_aliases
    assert "pool.master_data_sync.launch" in expected_aliases
    assert "pool.master_data_bootstrap.collection.stage" in expected_aliases
    assert result.created == len(expected_aliases)
    assert result.updated == 0
    assert result.unchanged == 0

    rows = list(
        OperationExposure.objects.filter(
            surface=OperationExposure.SURFACE_TEMPLATE,
            tenant__isnull=True,
            alias__in=expected_aliases,
        ).order_by("alias")
    )
    assert len(rows) == len(expected_aliases)
    for row in rows:
        assert row.alias in expected_aliases
        assert row.system_managed is True
        assert row.domain == OperationExposure.DOMAIN_POOL_RUNTIME
        assert row.status == OperationExposure.STATUS_PUBLISHED
        assert row.is_active is True
        assert row.capability == "pools.runtime"


@pytest.mark.django_db
def test_sync_pool_runtime_template_registry_is_idempotent() -> None:
    first = sync_pool_runtime_template_registry()
    second = sync_pool_runtime_template_registry()

    assert first.created == len(get_pool_runtime_template_aliases())
    assert second.created == 0
    assert second.updated == 0
    assert second.unchanged == len(get_pool_runtime_template_aliases())


@pytest.mark.django_db
def test_sync_pool_runtime_template_registry_updates_existing_alias() -> None:
    alias = "pool.prepare_input"
    definition = OperationDefinition.objects.create(
        tenant_scope="global",
        executor_kind=OperationDefinition.EXECUTOR_WORKFLOW,
        executor_payload={
            "operation_type": alias,
            "target_entity": "pool_run",
            "template_data": {"legacy": True},
        },
        contract_version=1,
        fingerprint="legacy-pool-prepare-input",
        status=OperationDefinition.STATUS_ACTIVE,
    )
    OperationExposure.objects.create(
        definition=definition,
        surface=OperationExposure.SURFACE_TEMPLATE,
        alias=alias,
        tenant=None,
        label="Legacy alias",
        description="legacy",
        is_active=False,
        capability="legacy.pool",
        contexts=["legacy"],
        display_order=0,
        capability_config={"legacy": True},
        status=OperationExposure.STATUS_DRAFT,
        system_managed=False,
        domain="",
    )

    result = sync_pool_runtime_template_registry()
    assert result.updated >= 1

    refreshed = OperationExposure.objects.get(
        surface=OperationExposure.SURFACE_TEMPLATE,
        tenant__isnull=True,
        alias=alias,
    )
    assert refreshed.system_managed is True
    assert refreshed.domain == OperationExposure.DOMAIN_POOL_RUNTIME
    assert refreshed.status == OperationExposure.STATUS_PUBLISHED
    assert refreshed.is_active is True
    assert refreshed.capability == "pools.runtime"
