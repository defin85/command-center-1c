from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Mapping

from django.utils import timezone

from .master_data_sync_invariants import build_outbound_dedupe_key
from .models import (
    PoolMasterDataEntityType,
    PoolMasterDataSyncOutbox,
    PoolMasterDataSyncOutboxStatus,
)


def build_master_data_mutation_payload_fingerprint(*, payload: Mapping[str, Any]) -> str:
    return sha256(_canonical_json(payload)).hexdigest()


def enqueue_master_data_sync_outbox_intent(
    *,
    tenant_id: str,
    database_id: str,
    entity_type: str,
    canonical_id: str,
    mutation_kind: str,
    payload: Mapping[str, Any],
    origin_system: str = "cc",
    origin_event_id: str = "",
) -> PoolMasterDataSyncOutbox:
    normalized_entity_type = str(entity_type or "").strip()
    if normalized_entity_type not in set(PoolMasterDataEntityType.values):
        raise ValueError(f"Unsupported master-data entity_type '{entity_type}'")

    normalized_canonical_id = str(canonical_id or "").strip()
    if not normalized_canonical_id:
        raise ValueError("canonical_id is required")

    normalized_mutation_kind = str(mutation_kind or "").strip()
    if not normalized_mutation_kind:
        raise ValueError("mutation_kind is required")

    normalized_origin_system = str(origin_system or "").strip() or "cc"
    payload_dict = dict(payload or {})
    payload_fingerprint = build_master_data_mutation_payload_fingerprint(payload=payload_dict)
    normalized_origin_event_id = str(origin_event_id or "").strip()
    if not normalized_origin_event_id:
        normalized_origin_event_id = (
            f"{normalized_mutation_kind}:{normalized_entity_type}:{normalized_canonical_id}:"
            f"{payload_fingerprint[:24]}"
        )

    dedupe_key = build_outbound_dedupe_key(
        tenant_id=str(tenant_id or "").strip(),
        database_id=str(database_id or "").strip(),
        entity_type=normalized_entity_type,
        canonical_id=normalized_canonical_id,
        mutation_kind=normalized_mutation_kind,
        payload_fingerprint=payload_fingerprint,
        origin_event_id=normalized_origin_event_id,
    )
    row, _created = PoolMasterDataSyncOutbox.objects.update_or_create(
        tenant_id=str(tenant_id or "").strip(),
        database_id=str(database_id or "").strip(),
        entity_type=normalized_entity_type,
        dedupe_key=dedupe_key,
        defaults={
            "status": PoolMasterDataSyncOutboxStatus.PENDING,
            "origin_system": normalized_origin_system,
            "origin_event_id": normalized_origin_event_id,
            "payload": {
                "mutation_kind": normalized_mutation_kind,
                "canonical_id": normalized_canonical_id,
                "payload": payload_dict,
                "payload_fingerprint": payload_fingerprint,
            },
            "available_at": timezone.now(),
            "last_error_code": "",
            "last_error": "",
        },
    )
    return row


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
