from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from apps.runtime_settings.models import RuntimeSetting, TenantRuntimeSettingOverride


POOL_MASTER_DATA_BOOTSTRAP_IMPORT_RUNTIME_KEY = "pools.master_data.bootstrap_import.enabled"
POOL_MASTER_DATA_BOOTSTRAP_IMPORT_ENV_KEY = "POOL_MASTER_DATA_BOOTSTRAP_IMPORT_ENABLED"
MASTER_DATA_BOOTSTRAP_IMPORT_CONFIG_INVALID = "MASTER_DATA_BOOTSTRAP_IMPORT_CONFIG_INVALID"


@dataclass(frozen=True)
class PoolMasterDataBootstrapImportFlagResolution:
    source: str
    raw_value: object
    value: bool | None


class MasterDataBootstrapImportConfigInvalidError(ValueError):
    def __init__(self, *, source: str, raw_value: object) -> None:
        self.code = MASTER_DATA_BOOTSTRAP_IMPORT_CONFIG_INVALID
        self.runtime_key = POOL_MASTER_DATA_BOOTSTRAP_IMPORT_RUNTIME_KEY
        self.source = source
        self.raw_value = raw_value
        self.detail = (
            f"Invalid bool value for '{self.runtime_key}' "
            f"from {self.source}: {self.raw_value!r}"
        )
        super().__init__(f"{self.code}: {self.detail}")


def _parse_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in {0, 1}:
            return bool(value)
        return None
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"1", "true", "yes", "on"}:
            return True
        if token in {"0", "false", "no", "off"}:
            return False
    return None


def resolve_pool_master_data_bootstrap_import_flag(
    *,
    tenant_id: str | None,
) -> PoolMasterDataBootstrapImportFlagResolution:
    if tenant_id:
        tenant_override = (
            TenantRuntimeSettingOverride.objects.filter(
                tenant_id=tenant_id,
                key=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_RUNTIME_KEY,
                status=TenantRuntimeSettingOverride.STATUS_PUBLISHED,
            )
            .values_list("value", flat=True)
            .first()
        )
        if tenant_override is not None:
            return PoolMasterDataBootstrapImportFlagResolution(
                source="tenant_override",
                raw_value=tenant_override,
                value=_parse_bool(tenant_override),
            )

    global_value = (
        RuntimeSetting.objects.filter(key=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_RUNTIME_KEY)
        .values_list("value", flat=True)
        .first()
    )
    if global_value is not None:
        return PoolMasterDataBootstrapImportFlagResolution(
            source="global",
            raw_value=global_value,
            value=_parse_bool(global_value),
        )

    env_value = getattr(settings, POOL_MASTER_DATA_BOOTSTRAP_IMPORT_ENV_KEY, False)
    return PoolMasterDataBootstrapImportFlagResolution(
        source="env_default",
        raw_value=env_value,
        value=_parse_bool(env_value),
    )


def is_pool_master_data_bootstrap_import_enabled(
    *,
    tenant_id: str | None = None,
    fail_closed_on_invalid: bool = False,
) -> bool:
    resolution = resolve_pool_master_data_bootstrap_import_flag(tenant_id=tenant_id)
    if resolution.value is None:
        if fail_closed_on_invalid:
            raise MasterDataBootstrapImportConfigInvalidError(
                source=resolution.source,
                raw_value=resolution.raw_value,
            )
        return False
    return bool(resolution.value)


def require_pool_master_data_bootstrap_import_enabled(*, tenant_id: str | None = None) -> bool:
    return is_pool_master_data_bootstrap_import_enabled(
        tenant_id=tenant_id,
        fail_closed_on_invalid=True,
    )

