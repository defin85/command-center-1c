import logging

from drf_spectacular.utils import extend_schema

from apps.runtime_settings.models import RuntimeSetting
from apps.runtime_settings.registry import RUNTIME_SETTINGS

logger = logging.getLogger("apps.api_internal.views")
exclude_schema = extend_schema(exclude=True)


def _ensure_runtime_defaults():
    for definition in RUNTIME_SETTINGS.values():
        RuntimeSetting.objects.get_or_create(
            key=definition.key,
            defaults={"value": definition.default},
        )


def _model_dump(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(by_alias=True)
    if hasattr(value, "dict"):
        return value.dict(by_alias=True)
    return value

