from __future__ import annotations

import pytest
from django.test.utils import override_settings

from apps.intercompany_pools.master_data_bootstrap_import_feature_flags import (
    MasterDataBootstrapImportConfigInvalidError,
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_RUNTIME_KEY,
    is_pool_master_data_bootstrap_import_enabled,
    resolve_pool_master_data_bootstrap_import_flag,
)
from apps.runtime_settings.models import RuntimeSetting, TenantRuntimeSettingOverride
from apps.tenancy.models import Tenant


@pytest.mark.django_db
def test_bootstrap_import_flag_uses_env_default_when_db_values_are_absent() -> None:
    with override_settings(POOL_MASTER_DATA_BOOTSTRAP_IMPORT_ENABLED=True):
        resolution = resolve_pool_master_data_bootstrap_import_flag(tenant_id=None)

    assert resolution.source == "env_default"
    assert resolution.raw_value is True
    assert resolution.value is True

    with override_settings(POOL_MASTER_DATA_BOOTSTRAP_IMPORT_ENABLED=True):
        assert is_pool_master_data_bootstrap_import_enabled() is True


@pytest.mark.django_db
def test_bootstrap_import_flag_prefers_global_setting_over_env_default() -> None:
    RuntimeSetting.objects.create(
        key=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_RUNTIME_KEY,
        value=False,
    )

    with override_settings(POOL_MASTER_DATA_BOOTSTRAP_IMPORT_ENABLED=True):
        resolution = resolve_pool_master_data_bootstrap_import_flag(tenant_id=None)
        enabled = is_pool_master_data_bootstrap_import_enabled()

    assert resolution.source == "global"
    assert resolution.raw_value is False
    assert resolution.value is False
    assert enabled is False


@pytest.mark.django_db
def test_bootstrap_import_flag_prefers_tenant_override_over_global() -> None:
    tenant = Tenant.objects.create(slug="tenant-md-bootstrap-flag", name="Tenant MD Bootstrap Flag")
    RuntimeSetting.objects.create(
        key=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_RUNTIME_KEY,
        value=False,
    )
    TenantRuntimeSettingOverride.objects.create(
        tenant=tenant,
        key=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_RUNTIME_KEY,
        value=True,
        status=TenantRuntimeSettingOverride.STATUS_PUBLISHED,
    )

    resolution = resolve_pool_master_data_bootstrap_import_flag(tenant_id=str(tenant.id))
    enabled = is_pool_master_data_bootstrap_import_enabled(tenant_id=str(tenant.id))

    assert resolution.source == "tenant_override"
    assert resolution.raw_value is True
    assert resolution.value is True
    assert enabled is True


@pytest.mark.django_db
def test_bootstrap_import_flag_fails_closed_on_invalid_value() -> None:
    RuntimeSetting.objects.create(
        key=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_RUNTIME_KEY,
        value="definitely-not-bool",
    )

    resolution = resolve_pool_master_data_bootstrap_import_flag(tenant_id=None)
    assert resolution.source == "global"
    assert resolution.raw_value == "definitely-not-bool"
    assert resolution.value is None
    assert is_pool_master_data_bootstrap_import_enabled() is False

    with pytest.raises(
        MasterDataBootstrapImportConfigInvalidError,
        match="MASTER_DATA_BOOTSTRAP_IMPORT_CONFIG_INVALID",
    ) as exc_info:
        is_pool_master_data_bootstrap_import_enabled(fail_closed_on_invalid=True)

    assert exc_info.value.code == "MASTER_DATA_BOOTSTRAP_IMPORT_CONFIG_INVALID"
    assert exc_info.value.source == "global"
    assert exc_info.value.raw_value == "definitely-not-bool"
