from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from apps.runtime_settings.models import RuntimeSetting, TenantRuntimeSettingOverride


POOL_MASTER_DATA_SYNC_ENABLED_RUNTIME_KEY = "pools.master_data.sync.enabled"
POOL_MASTER_DATA_SYNC_POLL_INTERVAL_RUNTIME_KEY = "pools.master_data.sync.poll_interval_seconds"
POOL_MASTER_DATA_SYNC_DISPATCH_BATCH_RUNTIME_KEY = "pools.master_data.sync.dispatch_batch_size"
POOL_MASTER_DATA_SYNC_RETRY_BACKOFF_RUNTIME_KEY = "pools.master_data.sync.max_retry_backoff_seconds"

POOL_MASTER_DATA_SYNC_ENABLED_ENV_KEY = "POOL_RUNTIME_MASTER_DATA_SYNC_ENABLED"
POOL_MASTER_DATA_SYNC_POLL_INTERVAL_ENV_KEY = "POOL_RUNTIME_MASTER_DATA_SYNC_POLL_INTERVAL_SECONDS"
POOL_MASTER_DATA_SYNC_DISPATCH_BATCH_ENV_KEY = "POOL_RUNTIME_MASTER_DATA_SYNC_DISPATCH_BATCH_SIZE"
POOL_MASTER_DATA_SYNC_RETRY_BACKOFF_ENV_KEY = "POOL_RUNTIME_MASTER_DATA_SYNC_MAX_RETRY_BACKOFF_SECONDS"

MASTER_DATA_SYNC_RUNTIME_CONFIG_INVALID = "MASTER_DATA_SYNC_RUNTIME_CONFIG_INVALID"


@dataclass(frozen=True)
class RuntimeSettingResolution:
    source: str
    raw_value: object


@dataclass(frozen=True)
class PoolMasterDataSyncRuntimeSettings:
    enabled: bool
    poll_interval_seconds: int
    dispatch_batch_size: int
    max_retry_backoff_seconds: int
    sources: dict[str, str]


class MasterDataSyncRuntimeConfigInvalidError(ValueError):
    def __init__(self, *, runtime_key: str, source: str, raw_value: object) -> None:
        self.code = MASTER_DATA_SYNC_RUNTIME_CONFIG_INVALID
        self.runtime_key = runtime_key
        self.source = source
        self.raw_value = raw_value
        self.detail = (
            f"Invalid runtime value for '{runtime_key}' from {source}: {raw_value!r}"
        )
        super().__init__(f"{self.code}: {self.detail}")

    def to_diagnostic(self) -> dict[str, object]:
        return {
            "error_code": self.code,
            "runtime_key": self.runtime_key,
            "source": self.source,
            "raw_value": repr(self.raw_value),
        }


def resolve_pool_master_data_sync_runtime_settings(
    *,
    tenant_id: str | None = None,
) -> dict[str, RuntimeSettingResolution]:
    return {
        POOL_MASTER_DATA_SYNC_ENABLED_RUNTIME_KEY: _resolve_runtime_setting(
            key=POOL_MASTER_DATA_SYNC_ENABLED_RUNTIME_KEY,
            tenant_id=tenant_id,
            env_key=POOL_MASTER_DATA_SYNC_ENABLED_ENV_KEY,
            env_default=False,
        ),
        POOL_MASTER_DATA_SYNC_POLL_INTERVAL_RUNTIME_KEY: _resolve_runtime_setting(
            key=POOL_MASTER_DATA_SYNC_POLL_INTERVAL_RUNTIME_KEY,
            tenant_id=tenant_id,
            env_key=POOL_MASTER_DATA_SYNC_POLL_INTERVAL_ENV_KEY,
            env_default=30,
        ),
        POOL_MASTER_DATA_SYNC_DISPATCH_BATCH_RUNTIME_KEY: _resolve_runtime_setting(
            key=POOL_MASTER_DATA_SYNC_DISPATCH_BATCH_RUNTIME_KEY,
            tenant_id=tenant_id,
            env_key=POOL_MASTER_DATA_SYNC_DISPATCH_BATCH_ENV_KEY,
            env_default=100,
        ),
        POOL_MASTER_DATA_SYNC_RETRY_BACKOFF_RUNTIME_KEY: _resolve_runtime_setting(
            key=POOL_MASTER_DATA_SYNC_RETRY_BACKOFF_RUNTIME_KEY,
            tenant_id=tenant_id,
            env_key=POOL_MASTER_DATA_SYNC_RETRY_BACKOFF_ENV_KEY,
            env_default=900,
        ),
    }


def get_pool_master_data_sync_runtime_settings(
    *,
    tenant_id: str | None = None,
    fail_closed_on_invalid: bool = False,
) -> PoolMasterDataSyncRuntimeSettings:
    resolved = resolve_pool_master_data_sync_runtime_settings(tenant_id=tenant_id)
    enabled = _coerce_bool(
        resolution=resolved[POOL_MASTER_DATA_SYNC_ENABLED_RUNTIME_KEY],
        runtime_key=POOL_MASTER_DATA_SYNC_ENABLED_RUNTIME_KEY,
        default=False,
        fail_closed_on_invalid=fail_closed_on_invalid,
    )
    poll_interval_seconds = _coerce_int(
        resolution=resolved[POOL_MASTER_DATA_SYNC_POLL_INTERVAL_RUNTIME_KEY],
        runtime_key=POOL_MASTER_DATA_SYNC_POLL_INTERVAL_RUNTIME_KEY,
        min_value=1,
        max_value=3600,
        default=30,
        fail_closed_on_invalid=fail_closed_on_invalid,
    )
    dispatch_batch_size = _coerce_int(
        resolution=resolved[POOL_MASTER_DATA_SYNC_DISPATCH_BATCH_RUNTIME_KEY],
        runtime_key=POOL_MASTER_DATA_SYNC_DISPATCH_BATCH_RUNTIME_KEY,
        min_value=1,
        max_value=1000,
        default=100,
        fail_closed_on_invalid=fail_closed_on_invalid,
    )
    max_retry_backoff_seconds = _coerce_int(
        resolution=resolved[POOL_MASTER_DATA_SYNC_RETRY_BACKOFF_RUNTIME_KEY],
        runtime_key=POOL_MASTER_DATA_SYNC_RETRY_BACKOFF_RUNTIME_KEY,
        min_value=1,
        max_value=7200,
        default=900,
        fail_closed_on_invalid=fail_closed_on_invalid,
    )
    return PoolMasterDataSyncRuntimeSettings(
        enabled=enabled,
        poll_interval_seconds=poll_interval_seconds,
        dispatch_batch_size=dispatch_batch_size,
        max_retry_backoff_seconds=max_retry_backoff_seconds,
        sources={key: value.source for key, value in resolved.items()},
    )


def require_pool_master_data_sync_runtime_settings(*, tenant_id: str | None = None) -> PoolMasterDataSyncRuntimeSettings:
    return get_pool_master_data_sync_runtime_settings(
        tenant_id=tenant_id,
        fail_closed_on_invalid=True,
    )


def _resolve_runtime_setting(
    *,
    key: str,
    tenant_id: str | None,
    env_key: str,
    env_default: object,
) -> RuntimeSettingResolution:
    if tenant_id:
        tenant_override = (
            TenantRuntimeSettingOverride.objects.filter(
                tenant_id=tenant_id,
                key=key,
                status=TenantRuntimeSettingOverride.STATUS_PUBLISHED,
            )
            .values_list("value", flat=True)
            .first()
        )
        if tenant_override is not None:
            return RuntimeSettingResolution(source="tenant_override", raw_value=tenant_override)

    global_value = RuntimeSetting.objects.filter(key=key).values_list("value", flat=True).first()
    if global_value is not None:
        return RuntimeSettingResolution(source="global", raw_value=global_value)

    env_value = getattr(settings, env_key, env_default)
    return RuntimeSettingResolution(source="env_default", raw_value=env_value)


def _coerce_bool(
    *,
    resolution: RuntimeSettingResolution,
    runtime_key: str,
    default: bool,
    fail_closed_on_invalid: bool,
) -> bool:
    parsed = _parse_bool(resolution.raw_value)
    if parsed is not None:
        return parsed
    if fail_closed_on_invalid:
        raise MasterDataSyncRuntimeConfigInvalidError(
            runtime_key=runtime_key,
            source=resolution.source,
            raw_value=resolution.raw_value,
        )
    return bool(default)


def _coerce_int(
    *,
    resolution: RuntimeSettingResolution,
    runtime_key: str,
    min_value: int,
    max_value: int,
    default: int,
    fail_closed_on_invalid: bool,
) -> int:
    parsed = _parse_int(resolution.raw_value)
    if parsed is not None and min_value <= parsed <= max_value:
        return parsed
    if fail_closed_on_invalid:
        raise MasterDataSyncRuntimeConfigInvalidError(
            runtime_key=runtime_key,
            source=resolution.source,
            raw_value=resolution.raw_value,
        )
    return int(default)


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


def _parse_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        token = value.strip()
        if not token:
            return None
        try:
            return int(token)
        except ValueError:
            return None
    return None
