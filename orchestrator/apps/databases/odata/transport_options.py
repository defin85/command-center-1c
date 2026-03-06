from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from apps.databases.models import Database


ODATA_TRANSPORT_METADATA_KEY = "odata_transport"
ODATA_VERIFY_TLS_METADATA_KEY = "verify_tls"


def resolve_database_odata_verify_tls(*, database: Database | None) -> bool:
    metadata = getattr(database, "metadata", None)
    if not isinstance(metadata, Mapping):
        return True
    transport = metadata.get(ODATA_TRANSPORT_METADATA_KEY)
    if not isinstance(transport, Mapping):
        return True
    return _coerce_bool(transport.get(ODATA_VERIFY_TLS_METADATA_KEY), default=True)


def _coerce_bool(raw_value: Any, *, default: bool) -> bool:
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, str):
        normalized = raw_value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default
