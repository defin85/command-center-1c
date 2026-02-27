from __future__ import annotations

from django.conf import settings


def is_pool_master_data_gate_enabled() -> bool:
    return bool(getattr(settings, "POOL_RUNTIME_MASTER_DATA_GATE_ENABLED", False))
