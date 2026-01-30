from __future__ import annotations

from dataclasses import dataclass

from apps.runtime_settings.models import RuntimeSetting, TenantRuntimeSettingOverride
from apps.runtime_settings.registry import RUNTIME_SETTINGS


@dataclass(frozen=True)
class EffectiveRuntimeSetting:
    key: str
    value: object
    source: str  # tenant_override | global | default


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

    return EffectiveRuntimeSetting(key=key, value=default_value, source="default")

