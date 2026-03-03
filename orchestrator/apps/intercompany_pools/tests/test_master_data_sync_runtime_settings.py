from __future__ import annotations

import pytest
from django.test.utils import override_settings

from apps.intercompany_pools.master_data_sync_runtime_settings import (
    MasterDataSyncRuntimeConfigInvalidError,
    POOL_MASTER_DATA_SYNC_DEFAULT_POLICY_RUNTIME_KEY,
    POOL_MASTER_DATA_SYNC_DISPATCH_BATCH_RUNTIME_KEY,
    POOL_MASTER_DATA_SYNC_ENABLED_RUNTIME_KEY,
    POOL_MASTER_DATA_SYNC_INBOUND_ENABLED_RUNTIME_KEY,
    POOL_MASTER_DATA_SYNC_OUTBOUND_ENABLED_RUNTIME_KEY,
    POOL_MASTER_DATA_SYNC_POLL_INTERVAL_RUNTIME_KEY,
    POOL_MASTER_DATA_SYNC_RETRY_BACKOFF_RUNTIME_KEY,
    get_pool_master_data_sync_runtime_settings,
    resolve_pool_master_data_sync_runtime_settings,
)
from apps.runtime_settings.models import RuntimeSetting, TenantRuntimeSettingOverride
from apps.tenancy.models import Tenant


@pytest.mark.django_db
def test_runtime_settings_use_env_defaults_when_db_values_are_absent() -> None:
    with override_settings(
        POOL_RUNTIME_MASTER_DATA_SYNC_ENABLED=True,
        POOL_RUNTIME_MASTER_DATA_SYNC_INBOUND_ENABLED=False,
        POOL_RUNTIME_MASTER_DATA_SYNC_OUTBOUND_ENABLED=True,
        POOL_RUNTIME_MASTER_DATA_SYNC_DEFAULT_POLICY="bidirectional",
        POOL_RUNTIME_MASTER_DATA_SYNC_POLL_INTERVAL_SECONDS=45,
        POOL_RUNTIME_MASTER_DATA_SYNC_DISPATCH_BATCH_SIZE=150,
        POOL_RUNTIME_MASTER_DATA_SYNC_MAX_RETRY_BACKOFF_SECONDS=1200,
    ):
        resolved = resolve_pool_master_data_sync_runtime_settings(tenant_id=None)
        effective = get_pool_master_data_sync_runtime_settings()

    assert resolved[POOL_MASTER_DATA_SYNC_ENABLED_RUNTIME_KEY].source == "env_default"
    assert resolved[POOL_MASTER_DATA_SYNC_INBOUND_ENABLED_RUNTIME_KEY].source == "env_default"
    assert resolved[POOL_MASTER_DATA_SYNC_OUTBOUND_ENABLED_RUNTIME_KEY].source == "env_default"
    assert resolved[POOL_MASTER_DATA_SYNC_DEFAULT_POLICY_RUNTIME_KEY].source == "env_default"
    assert resolved[POOL_MASTER_DATA_SYNC_POLL_INTERVAL_RUNTIME_KEY].source == "env_default"
    assert resolved[POOL_MASTER_DATA_SYNC_DISPATCH_BATCH_RUNTIME_KEY].source == "env_default"
    assert resolved[POOL_MASTER_DATA_SYNC_RETRY_BACKOFF_RUNTIME_KEY].source == "env_default"
    assert effective.enabled is True
    assert effective.inbound_enabled is False
    assert effective.outbound_enabled is True
    assert effective.default_policy == "bidirectional"
    assert effective.poll_interval_seconds == 45
    assert effective.dispatch_batch_size == 150
    assert effective.max_retry_backoff_seconds == 1200


@pytest.mark.django_db
def test_runtime_settings_precedence_tenant_override_over_global_and_env() -> None:
    tenant = Tenant.objects.create(slug="sync-runtime-tenant", name="Sync Runtime Tenant")
    RuntimeSetting.objects.create(key=POOL_MASTER_DATA_SYNC_ENABLED_RUNTIME_KEY, value=False)
    RuntimeSetting.objects.create(key=POOL_MASTER_DATA_SYNC_INBOUND_ENABLED_RUNTIME_KEY, value=False)
    RuntimeSetting.objects.create(key=POOL_MASTER_DATA_SYNC_OUTBOUND_ENABLED_RUNTIME_KEY, value=True)
    RuntimeSetting.objects.create(key=POOL_MASTER_DATA_SYNC_DEFAULT_POLICY_RUNTIME_KEY, value="cc_master")
    RuntimeSetting.objects.create(key=POOL_MASTER_DATA_SYNC_POLL_INTERVAL_RUNTIME_KEY, value=90)
    RuntimeSetting.objects.create(key=POOL_MASTER_DATA_SYNC_DISPATCH_BATCH_RUNTIME_KEY, value=300)
    RuntimeSetting.objects.create(key=POOL_MASTER_DATA_SYNC_RETRY_BACKOFF_RUNTIME_KEY, value=1800)
    TenantRuntimeSettingOverride.objects.create(
        tenant=tenant,
        key=POOL_MASTER_DATA_SYNC_ENABLED_RUNTIME_KEY,
        value=True,
        status=TenantRuntimeSettingOverride.STATUS_PUBLISHED,
    )
    TenantRuntimeSettingOverride.objects.create(
        tenant=tenant,
        key=POOL_MASTER_DATA_SYNC_POLL_INTERVAL_RUNTIME_KEY,
        value=15,
        status=TenantRuntimeSettingOverride.STATUS_PUBLISHED,
    )
    TenantRuntimeSettingOverride.objects.create(
        tenant=tenant,
        key=POOL_MASTER_DATA_SYNC_OUTBOUND_ENABLED_RUNTIME_KEY,
        value=False,
        status=TenantRuntimeSettingOverride.STATUS_PUBLISHED,
    )
    TenantRuntimeSettingOverride.objects.create(
        tenant=tenant,
        key=POOL_MASTER_DATA_SYNC_DEFAULT_POLICY_RUNTIME_KEY,
        value="bidirectional",
        status=TenantRuntimeSettingOverride.STATUS_PUBLISHED,
    )

    with override_settings(
        POOL_RUNTIME_MASTER_DATA_SYNC_ENABLED=False,
        POOL_RUNTIME_MASTER_DATA_SYNC_INBOUND_ENABLED=True,
        POOL_RUNTIME_MASTER_DATA_SYNC_OUTBOUND_ENABLED=True,
        POOL_RUNTIME_MASTER_DATA_SYNC_DEFAULT_POLICY="ib_master",
        POOL_RUNTIME_MASTER_DATA_SYNC_POLL_INTERVAL_SECONDS=120,
        POOL_RUNTIME_MASTER_DATA_SYNC_DISPATCH_BATCH_SIZE=10,
        POOL_RUNTIME_MASTER_DATA_SYNC_MAX_RETRY_BACKOFF_SECONDS=10,
    ):
        effective = get_pool_master_data_sync_runtime_settings(tenant_id=str(tenant.id))

    assert effective.enabled is True
    assert effective.inbound_enabled is False
    assert effective.outbound_enabled is False
    assert effective.default_policy == "bidirectional"
    assert effective.poll_interval_seconds == 15
    assert effective.dispatch_batch_size == 300
    assert effective.max_retry_backoff_seconds == 1800
    assert effective.sources[POOL_MASTER_DATA_SYNC_ENABLED_RUNTIME_KEY] == "tenant_override"
    assert effective.sources[POOL_MASTER_DATA_SYNC_INBOUND_ENABLED_RUNTIME_KEY] == "global"
    assert effective.sources[POOL_MASTER_DATA_SYNC_OUTBOUND_ENABLED_RUNTIME_KEY] == "tenant_override"
    assert effective.sources[POOL_MASTER_DATA_SYNC_DEFAULT_POLICY_RUNTIME_KEY] == "tenant_override"
    assert effective.sources[POOL_MASTER_DATA_SYNC_POLL_INTERVAL_RUNTIME_KEY] == "tenant_override"
    assert effective.sources[POOL_MASTER_DATA_SYNC_DISPATCH_BATCH_RUNTIME_KEY] == "global"
    assert effective.sources[POOL_MASTER_DATA_SYNC_RETRY_BACKOFF_RUNTIME_KEY] == "global"


@pytest.mark.django_db
def test_runtime_settings_ignore_draft_tenant_override() -> None:
    tenant = Tenant.objects.create(slug="sync-runtime-draft", name="Sync Runtime Draft")
    RuntimeSetting.objects.create(key=POOL_MASTER_DATA_SYNC_ENABLED_RUNTIME_KEY, value=True)
    TenantRuntimeSettingOverride.objects.create(
        tenant=tenant,
        key=POOL_MASTER_DATA_SYNC_ENABLED_RUNTIME_KEY,
        value=False,
        status=TenantRuntimeSettingOverride.STATUS_DRAFT,
    )

    effective = get_pool_master_data_sync_runtime_settings(tenant_id=str(tenant.id))
    assert effective.enabled is True
    assert effective.sources[POOL_MASTER_DATA_SYNC_ENABLED_RUNTIME_KEY] == "global"


@pytest.mark.django_db
def test_runtime_settings_fail_closed_on_invalid_values() -> None:
    RuntimeSetting.objects.create(key=POOL_MASTER_DATA_SYNC_POLL_INTERVAL_RUNTIME_KEY, value="invalid-int")
    RuntimeSetting.objects.create(key=POOL_MASTER_DATA_SYNC_DEFAULT_POLICY_RUNTIME_KEY, value="unsupported")

    effective = get_pool_master_data_sync_runtime_settings()
    assert effective.poll_interval_seconds == 30
    assert effective.default_policy == "cc_master"

    with pytest.raises(MasterDataSyncRuntimeConfigInvalidError) as exc_info:
        get_pool_master_data_sync_runtime_settings(fail_closed_on_invalid=True)

    assert exc_info.value.code == "MASTER_DATA_SYNC_RUNTIME_CONFIG_INVALID"
    assert exc_info.value.runtime_key in {
        POOL_MASTER_DATA_SYNC_POLL_INTERVAL_RUNTIME_KEY,
        POOL_MASTER_DATA_SYNC_DEFAULT_POLICY_RUNTIME_KEY,
    }
    assert exc_info.value.source == "global"
