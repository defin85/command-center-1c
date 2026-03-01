from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from apps.runtime_settings.models import RuntimeSetting, TenantRuntimeSettingOverride
from apps.runtime_settings.registry import RUNTIME_SETTINGS


@dataclass(frozen=True)
class EffectiveRuntimeSetting:
    key: str
    value: object
    source: str  # tenant_override | global | env_default | default


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


def _resolve_env_default_value(*, definition) -> object | None:
    env_key = str(getattr(definition, "env_default_setting", "") or "").strip()
    if not env_key:
        return None

    raw_env_value = getattr(settings, env_key, definition.default)
    if definition.value_type == "bool":
        parsed = _parse_bool(raw_env_value)
        if parsed is None:
            fallback = _parse_bool(definition.default)
            return fallback if fallback is not None else False
        return parsed
    return raw_env_value


def get_effective_runtime_setting(key: str, tenant_id: str | None) -> EffectiveRuntimeSetting:
    definition = RUNTIME_SETTINGS.get(key)
    default_value = definition.default if definition else {}

    if tenant_id:
        override = (
            TenantRuntimeSettingOverride.objects.filter(tenant_id=tenant_id, key=key, status=TenantRuntimeSettingOverride.STATUS_PUBLISHED)
            .values_list("value", flat=True)
            .first()
        )
        if override is not None:
            return EffectiveRuntimeSetting(key=key, value=override, source="tenant_override")

    global_value = RuntimeSetting.objects.filter(key=key).values_list("value", flat=True).first()
    if global_value is not None:
        return EffectiveRuntimeSetting(key=key, value=global_value, source="global")

    if definition is not None:
        env_default = _resolve_env_default_value(definition=definition)
        if env_default is not None:
            return EffectiveRuntimeSetting(key=key, value=env_default, source="env_default")

    return EffectiveRuntimeSetting(key=key, value=default_value, source="default")
