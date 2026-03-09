from __future__ import annotations

import pytest
from django.test.utils import override_settings

from apps.intercompany_pools.master_data_feature_flags import (
    MasterDataGateConfigInvalidError,
    POOL_MASTER_DATA_GATE_RUNTIME_KEY,
    is_pool_master_data_gate_enabled,
    resolve_pool_master_data_gate_flag,
)
from apps.runtime_settings.models import RuntimeSetting, TenantRuntimeSettingOverride
from apps.tenancy.models import Tenant


@pytest.mark.django_db
def test_master_data_gate_flag_uses_disabled_env_default_when_db_values_are_absent() -> None:
    with override_settings(POOL_RUNTIME_MASTER_DATA_GATE_ENABLED=False):
        resolution = resolve_pool_master_data_gate_flag(tenant_id=None)

    assert resolution.source == "env_default"
    assert resolution.raw_value is False
    assert resolution.value is False

    with override_settings(POOL_RUNTIME_MASTER_DATA_GATE_ENABLED=False):
        assert is_pool_master_data_gate_enabled() is False


@pytest.mark.django_db
def test_master_data_gate_flag_prefers_global_setting_over_env_default() -> None:
    RuntimeSetting.objects.create(
        key=POOL_MASTER_DATA_GATE_RUNTIME_KEY,
        value=False,
    )

    with override_settings(POOL_RUNTIME_MASTER_DATA_GATE_ENABLED=True):
        resolution = resolve_pool_master_data_gate_flag(tenant_id=None)
        enabled = is_pool_master_data_gate_enabled()

    assert resolution.source == "global"
    assert resolution.raw_value is False
    assert resolution.value is False
    assert enabled is False


@pytest.mark.django_db
def test_master_data_gate_flag_prefers_tenant_override_over_global() -> None:
    tenant = Tenant.objects.create(slug="tenant-md-gate", name="Tenant MD Gate")
    RuntimeSetting.objects.create(
        key=POOL_MASTER_DATA_GATE_RUNTIME_KEY,
        value=False,
    )
    TenantRuntimeSettingOverride.objects.create(
        tenant=tenant,
        key=POOL_MASTER_DATA_GATE_RUNTIME_KEY,
        value=True,
        status=TenantRuntimeSettingOverride.STATUS_PUBLISHED,
    )

    resolution = resolve_pool_master_data_gate_flag(tenant_id=str(tenant.id))
    enabled = is_pool_master_data_gate_enabled(tenant_id=str(tenant.id))

    assert resolution.source == "tenant_override"
    assert resolution.raw_value is True
    assert resolution.value is True
    assert enabled is True


@pytest.mark.django_db
def test_master_data_gate_flag_ignores_draft_override() -> None:
    tenant = Tenant.objects.create(slug="tenant-md-gate-draft", name="Tenant MD Gate Draft")
    RuntimeSetting.objects.create(
        key=POOL_MASTER_DATA_GATE_RUNTIME_KEY,
        value=True,
    )
    TenantRuntimeSettingOverride.objects.create(
        tenant=tenant,
        key=POOL_MASTER_DATA_GATE_RUNTIME_KEY,
        value=False,
        status=TenantRuntimeSettingOverride.STATUS_DRAFT,
    )

    resolution = resolve_pool_master_data_gate_flag(tenant_id=str(tenant.id))
    enabled = is_pool_master_data_gate_enabled(tenant_id=str(tenant.id))

    assert resolution.source == "global"
    assert resolution.value is True
    assert enabled is True


@pytest.mark.django_db
def test_master_data_gate_flag_fails_closed_on_invalid_effective_value() -> None:
    RuntimeSetting.objects.create(
        key=POOL_MASTER_DATA_GATE_RUNTIME_KEY,
        value="definitely-not-bool",
    )

    resolution = resolve_pool_master_data_gate_flag(tenant_id=None)
    assert resolution.source == "global"
    assert resolution.raw_value == "definitely-not-bool"
    assert resolution.value is None
    assert is_pool_master_data_gate_enabled() is False

    with pytest.raises(
        MasterDataGateConfigInvalidError,
        match="MASTER_DATA_GATE_CONFIG_INVALID",
    ) as exc_info:
        is_pool_master_data_gate_enabled(fail_closed_on_invalid=True)

    assert exc_info.value.code == "MASTER_DATA_GATE_CONFIG_INVALID"
    assert exc_info.value.source == "global"
    assert exc_info.value.raw_value == "definitely-not-bool"
