from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from django.utils import timezone

from .master_data_sync_outbox import build_master_data_mutation_payload_fingerprint
from .models import PoolMasterDataBinding, PoolMasterDataSyncOutbox


def apply_master_data_outbox_to_ib(
    *,
    outbox: PoolMasterDataSyncOutbox,
    ib_apply: Callable[[PoolMasterDataSyncOutbox], dict | None],
) -> dict[str, Any]:
    payload = dict(outbox.payload or {})
    mutation_kind = str(payload.get("mutation_kind") or "").strip()
    payload_data = payload.get("payload")
    payload_data_dict = dict(payload_data) if isinstance(payload_data, dict) else {}
    payload_fingerprint = str(payload.get("payload_fingerprint") or "").strip()
    if not payload_fingerprint:
        payload_fingerprint = build_master_data_mutation_payload_fingerprint(payload=payload_data_dict)

    binding = _resolve_binding_for_outbox(
        outbox=outbox,
        mutation_kind=mutation_kind,
        payload_data=payload_data_dict,
    )
    now = timezone.now()

    if binding is not None and str(binding.fingerprint or "").strip() == payload_fingerprint:
        _append_binding_sync_audit(
            binding=binding,
            audit_event={
                "event": "idempotent_skip",
                "applied_at": now.isoformat(),
                "origin_system": str(outbox.origin_system or ""),
                "origin_event_id": str(outbox.origin_event_id or ""),
                "dedupe_key": str(outbox.dedupe_key or ""),
                "payload_fingerprint": payload_fingerprint,
            },
        )
        binding.last_synced_at = now
        binding.save(update_fields=["last_synced_at", "metadata", "updated_at"])
        return {
            "applied": False,
            "idempotent": True,
            "binding_updated": True,
            "payload_fingerprint": payload_fingerprint,
        }

    transport_result = ib_apply(outbox)
    sanitized_transport_result = _sanitize_value(transport_result)

    binding_updated = False
    if binding is not None:
        binding.fingerprint = payload_fingerprint
        binding.last_synced_at = now
        _append_binding_sync_audit(
            binding=binding,
            audit_event={
                "event": "applied",
                "applied_at": now.isoformat(),
                "origin_system": str(outbox.origin_system or ""),
                "origin_event_id": str(outbox.origin_event_id or ""),
                "dedupe_key": str(outbox.dedupe_key or ""),
                "payload_fingerprint": payload_fingerprint,
                "transport_result": sanitized_transport_result,
            },
        )
        binding.save(update_fields=["fingerprint", "last_synced_at", "metadata", "updated_at"])
        binding_updated = True

    return {
        "applied": True,
        "idempotent": False,
        "binding_updated": binding_updated,
        "payload_fingerprint": payload_fingerprint,
        "transport_result": sanitized_transport_result,
    }


def _resolve_binding_for_outbox(
    *,
    outbox: PoolMasterDataSyncOutbox,
    mutation_kind: str,
    payload_data: dict[str, Any],
) -> PoolMasterDataBinding | None:
    if mutation_kind != "binding_upsert":
        return None

    canonical_id = str(payload_data.get("canonical_id") or "").strip()
    if not canonical_id:
        return None

    queryset = PoolMasterDataBinding.objects.filter(
        tenant_id=outbox.tenant_id,
        database_id=outbox.database_id,
        entity_type=str(outbox.entity_type or ""),
        canonical_id=canonical_id,
    )
    ib_catalog_kind = str(payload_data.get("ib_catalog_kind") or "").strip()
    owner_counterparty_canonical_id = str(payload_data.get("owner_counterparty_canonical_id") or "").strip()
    if ib_catalog_kind:
        queryset = queryset.filter(ib_catalog_kind=ib_catalog_kind)
    if owner_counterparty_canonical_id:
        queryset = queryset.filter(owner_counterparty_canonical_id=owner_counterparty_canonical_id)
    return queryset.order_by("-updated_at", "-created_at").first()


def _append_binding_sync_audit(*, binding: PoolMasterDataBinding, audit_event: dict[str, Any]) -> None:
    metadata = dict(binding.metadata or {})
    audit = metadata.get("sync_audit")
    history = list(audit) if isinstance(audit, list) else []
    history.append(audit_event)
    metadata["sync_audit"] = history[-20:]
    binding.metadata = metadata


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, nested_value in value.items():
            key_token = str(key or "").strip().lower()
            if _is_sensitive_key(key_token):
                sanitized[key] = "***"
                continue
            sanitized[key] = _sanitize_value(nested_value)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _is_sensitive_key(key: str) -> bool:
    return any(
        token in key
        for token in ("password", "token", "secret", "authorization", "api_key", "apikey")
    )
