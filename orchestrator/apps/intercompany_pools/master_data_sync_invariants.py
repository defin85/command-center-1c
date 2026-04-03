from __future__ import annotations

from dataclasses import dataclass
import hashlib

from apps.intercompany_pools.master_data_registry import normalize_pool_master_data_entity_type


MASTER_DATA_SYNC_INVARIANT_INVALID = "MASTER_DATA_SYNC_INVARIANT_INVALID"
OUTBOUND_DEDUPE_SCHEMA_VERSION = "outbound.v1"
INBOUND_DEDUPE_SCHEMA_VERSION = "inbound.v1"


class MasterDataSyncInvariantError(ValueError):
    def __init__(self, *, detail: str) -> None:
        self.code = MASTER_DATA_SYNC_INVARIANT_INVALID
        self.detail = str(detail)
        super().__init__(f"{self.code}: {self.detail}")

    def to_diagnostic(self) -> dict[str, str]:
        return {"error_code": self.code, "detail": self.detail}


@dataclass(frozen=True)
class OriginIdentifiers:
    origin_system: str
    origin_event_id: str


def _require_token(name: str, value: object) -> str:
    token = str(value or "").strip()
    if not token:
        raise MasterDataSyncInvariantError(detail=f"{name} is required")
    return token


def _require_entity_type(entity_type: str) -> str:
    normalized = _require_token("entity_type", entity_type)
    try:
        return normalize_pool_master_data_entity_type(normalized)
    except ValueError as exc:
        raise MasterDataSyncInvariantError(detail=str(exc)) from exc


def require_origin_identifiers(*, origin_system: str, origin_event_id: str) -> OriginIdentifiers:
    return OriginIdentifiers(
        origin_system=_require_token("origin_system", origin_system),
        origin_event_id=_require_token("origin_event_id", origin_event_id),
    )


def _hash_tokens(tokens: list[str]) -> str:
    payload = "|".join(tokens).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_outbound_dedupe_key(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    canonical_id: str,
    mutation_kind: str,
    payload_fingerprint: str,
    origin_event_id: str,
) -> str:
    return _hash_tokens(
        [
            OUTBOUND_DEDUPE_SCHEMA_VERSION,
            _require_token("tenant_id", tenant_id),
            _require_token("database_id", database_id),
            _require_entity_type(entity_type),
            _require_token("canonical_id", canonical_id),
            _require_token("mutation_kind", mutation_kind),
            _require_token("payload_fingerprint", payload_fingerprint),
            _require_token("origin_event_id", origin_event_id),
        ]
    )


def build_inbound_dedupe_fingerprint(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    origin_system: str,
    origin_event_id: str,
    payload_fingerprint: str,
) -> str:
    origin = require_origin_identifiers(
        origin_system=origin_system,
        origin_event_id=origin_event_id,
    )
    return _hash_tokens(
        [
            INBOUND_DEDUPE_SCHEMA_VERSION,
            _require_token("tenant_id", tenant_id),
            _require_token("database_id", database_id),
            _require_entity_type(entity_type),
            origin.origin_system,
            origin.origin_event_id,
            _require_token("payload_fingerprint", payload_fingerprint),
        ]
    )
