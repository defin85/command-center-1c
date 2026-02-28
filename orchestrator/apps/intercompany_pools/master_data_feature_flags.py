from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from apps.runtime_settings.models import RuntimeSetting, TenantRuntimeSettingOverride


POOL_MASTER_DATA_GATE_RUNTIME_KEY = "pools.master_data.gate_enabled"
POOL_MASTER_DATA_GATE_ENV_KEY = "POOL_RUNTIME_MASTER_DATA_GATE_ENABLED"
MASTER_DATA_GATE_CONFIG_INVALID = "MASTER_DATA_GATE_CONFIG_INVALID"


@dataclass(frozen=True)
class PoolMasterDataGateResolution:
    source: str
    raw_value: object
    value: bool | None


class MasterDataGateConfigInvalidError(ValueError):
    def __init__(self, *, source: str, raw_value: object) -> None:
        self.code = MASTER_DATA_GATE_CONFIG_INVALID
        self.runtime_key = POOL_MASTER_DATA_GATE_RUNTIME_KEY
        self.source = source
        self.raw_value = raw_value
        self.detail = (
            f"Invalid bool value for '{self.runtime_key}' "
            f"from {self.source}: {self.raw_value!r}"
        )
        super().__init__(f"{self.code}: {self.detail}")

    def to_diagnostic(self) -> dict[str, object]:
        return {
            "error_code": self.code,
            "runtime_key": self.runtime_key,
            "source": self.source,
            "raw_value": repr(self.raw_value),
        }


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


def resolve_pool_master_data_gate_flag(*, tenant_id: str | None) -> PoolMasterDataGateResolution:
    if tenant_id:
        tenant_override = (
            TenantRuntimeSettingOverride.objects.filter(
                tenant_id=tenant_id,
                key=POOL_MASTER_DATA_GATE_RUNTIME_KEY,
                status=TenantRuntimeSettingOverride.STATUS_PUBLISHED,
            )
            .values_list("value", flat=True)
            .first()
        )
        if tenant_override is not None:
            return PoolMasterDataGateResolution(
                source="tenant_override",
                raw_value=tenant_override,
                value=_parse_bool(tenant_override),
            )

    global_value = (
        RuntimeSetting.objects.filter(key=POOL_MASTER_DATA_GATE_RUNTIME_KEY)
        .values_list("value", flat=True)
        .first()
    )
    if global_value is not None:
        return PoolMasterDataGateResolution(
            source="global",
            raw_value=global_value,
            value=_parse_bool(global_value),
        )

    env_value = getattr(settings, POOL_MASTER_DATA_GATE_ENV_KEY, False)
    return PoolMasterDataGateResolution(
        source="env_default",
        raw_value=env_value,
        value=_parse_bool(env_value),
    )


def is_pool_master_data_gate_enabled(
    *,
    tenant_id: str | None = None,
    fail_closed_on_invalid: bool = False,
) -> bool:
    resolution = resolve_pool_master_data_gate_flag(tenant_id=tenant_id)
    if resolution.value is None:
        if fail_closed_on_invalid:
            raise MasterDataGateConfigInvalidError(
                source=resolution.source,
                raw_value=resolution.raw_value,
            )
        return False
    return resolution.value


def require_pool_master_data_gate_enabled(*, tenant_id: str | None = None) -> bool:
    return is_pool_master_data_gate_enabled(
        tenant_id=tenant_id,
        fail_closed_on_invalid=True,
    )
