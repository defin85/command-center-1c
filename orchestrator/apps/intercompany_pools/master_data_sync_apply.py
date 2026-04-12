from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Mapping

from django.utils import timezone

from .master_data_bindings import upsert_pool_master_data_binding
from .models import PoolMasterBindingSyncStatus, PoolMasterItem
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
        _sync_item_metadata_from_binding(
            outbox=outbox,
            mutation_kind=mutation_kind,
            binding=binding,
            payload_data=payload_data_dict,
        )
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

    binding, binding_updated = _finalize_binding_after_transport(
        outbox=outbox,
        mutation_kind=mutation_kind,
        payload_data=payload_data_dict,
        payload_fingerprint=payload_fingerprint,
        binding=binding,
        transport_result=sanitized_transport_result,
        now=now,
    )

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
    if mutation_kind not in {"binding_upsert", "item_upsert"}:
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
    if mutation_kind == "binding_upsert":
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


def _finalize_binding_after_transport(
    *,
    outbox: PoolMasterDataSyncOutbox,
    mutation_kind: str,
    payload_data: dict[str, Any],
    payload_fingerprint: str,
    binding: PoolMasterDataBinding | None,
    transport_result: Any,
    now,
) -> tuple[PoolMasterDataBinding | None, bool]:
    direct_binding_synced = False
    resolved_binding = binding
    if mutation_kind == "item_upsert":
        resolved_binding = _sync_item_binding_after_transport(
            outbox=outbox,
            payload_data=payload_data,
            payload_fingerprint=payload_fingerprint,
            binding=binding,
            transport_result=transport_result,
        )
        direct_binding_synced = resolved_binding is not None

    if resolved_binding is None:
        return None, direct_binding_synced

    resolved_binding.fingerprint = payload_fingerprint
    resolved_binding.last_synced_at = now
    _append_binding_sync_audit(
        binding=resolved_binding,
        audit_event={
            "event": "applied",
            "applied_at": now.isoformat(),
            "origin_system": str(outbox.origin_system or ""),
            "origin_event_id": str(outbox.origin_event_id or ""),
            "dedupe_key": str(outbox.dedupe_key or ""),
            "payload_fingerprint": payload_fingerprint,
            "transport_result": transport_result,
        },
    )
    resolved_binding.save(update_fields=["fingerprint", "last_synced_at", "metadata", "updated_at"])
    _sync_item_metadata_from_binding(
        outbox=outbox,
        mutation_kind=mutation_kind,
        binding=resolved_binding,
        payload_data=payload_data,
    )
    return resolved_binding, True


def _sync_item_binding_after_transport(
    *,
    outbox: PoolMasterDataSyncOutbox,
    payload_data: dict[str, Any],
    payload_fingerprint: str,
    binding: PoolMasterDataBinding | None,
    transport_result: Any,
) -> PoolMasterDataBinding | None:
    canonical_id = str(payload_data.get("canonical_id") or "").strip()
    if not canonical_id:
        return binding
    transport_payload = transport_result if isinstance(transport_result, Mapping) else {}
    ib_ref_key = str(transport_payload.get("ib_ref_key") or "").strip()
    if not ib_ref_key and binding is not None:
        ib_ref_key = str(binding.ib_ref_key or "").strip()
    if not ib_ref_key:
        return binding

    binding_metadata = dict(binding.metadata or {}) if binding is not None else {}
    result = upsert_pool_master_data_binding(
        tenant=outbox.tenant,
        entity_type=str(outbox.entity_type),
        canonical_id=canonical_id,
        database=outbox.database,
        ib_ref_key=ib_ref_key,
        existing_binding=binding,
        sync_status=PoolMasterBindingSyncStatus.UPSERTED,
        fingerprint=payload_fingerprint,
        metadata=binding_metadata,
        origin_system="ib",
        origin_event_id=f"master-data-sync-apply:{outbox.id}",
    )
    return result.binding


def _sync_item_metadata_from_binding(
    *,
    outbox: PoolMasterDataSyncOutbox,
    mutation_kind: str,
    binding: PoolMasterDataBinding | None,
    payload_data: dict[str, Any],
) -> None:
    if mutation_kind != "item_upsert" or binding is None:
        return
    canonical_id = str(payload_data.get("canonical_id") or "").strip()
    if not canonical_id:
        return
    item = PoolMasterItem.objects.filter(
        tenant_id=outbox.tenant_id,
        canonical_id=canonical_id,
    ).first()
    if item is None:
        return
    metadata = dict(item.metadata or {})
    next_metadata = _merge_item_binding_metadata(
        metadata=metadata,
        database_id=str(outbox.database_id),
        ib_ref_key=str(binding.ib_ref_key or "").strip(),
        payload_data=payload_data,
    )
    if next_metadata == metadata:
        return
    item.metadata = next_metadata
    item.save(update_fields=["metadata", "updated_at"])


def _merge_item_binding_metadata(
    *,
    metadata: dict[str, Any],
    database_id: str,
    ib_ref_key: str,
    payload_data: dict[str, Any],
) -> dict[str, Any]:
    next_metadata = dict(metadata)
    ib_ref_keys_raw = next_metadata.get("ib_ref_keys")
    ib_ref_keys = dict(ib_ref_keys_raw) if isinstance(ib_ref_keys_raw, Mapping) else {}
    changed = False
    if ib_ref_key and ib_ref_keys.get(database_id) != ib_ref_key:
        ib_ref_keys[database_id] = ib_ref_key
        changed = True
    nested_metadata = payload_data.get("metadata")
    payload_metadata = dict(nested_metadata) if isinstance(nested_metadata, Mapping) else {}
    for field_name in ("item_kind_ref", "unit_ref", "code", "full_name"):
        value = str(payload_metadata.get(field_name) or "").strip()
        if value and str(next_metadata.get(field_name) or "").strip() != value:
            next_metadata[field_name] = value
            changed = True
    is_service = payload_metadata.get("is_service")
    if isinstance(is_service, bool) and next_metadata.get("is_service") is not is_service:
        next_metadata["is_service"] = is_service
        changed = True
    if changed:
        next_metadata["ib_ref_keys"] = ib_ref_keys
    return next_metadata
