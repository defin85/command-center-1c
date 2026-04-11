from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.databases.models import Database

from .master_data_registry import (
    POOL_MASTER_DATA_CAPABILITY_CROSS_INFOBASE_DEDUPE,
    get_pool_master_data_registry_entry,
    normalize_pool_master_data_entity_type,
    supports_pool_master_data_capability,
)
from .master_data_sync_redaction import sanitize_master_data_sync_text, sanitize_master_data_sync_value
from .models import (
    PoolMasterContract,
    PoolMasterDataDedupeCluster,
    PoolMasterDataDedupeClusterStatus,
    PoolMasterDataDedupeReviewItem,
    PoolMasterDataDedupeReviewStatus,
    PoolMasterDataEntityType,
    PoolMasterDataSourceRecord,
    PoolMasterDataSourceRecordResolutionStatus,
    PoolMasterGLAccount,
    PoolMasterItem,
    PoolMasterParty,
    PoolMasterTaxProfile,
)


User = get_user_model()

MASTER_DATA_DEDUPE_REVIEW_REQUIRED = "MASTER_DATA_DEDUPE_REVIEW_REQUIRED"
MASTER_DATA_DEDUPE_CAPABILITY_DISABLED = "MASTER_DATA_DEDUPE_CAPABILITY_DISABLED"
MASTER_DATA_DEDUPE_INVALID_ACTION = "MASTER_DATA_DEDUPE_INVALID_ACTION"
MASTER_DATA_DEDUPE_REVIEW_ITEM_NOT_FOUND = "MASTER_DATA_DEDUPE_REVIEW_ITEM_NOT_FOUND"
MASTER_DATA_DEDUPE_MULTIPLE_ACTIVE_CLUSTERS = "MASTER_DATA_DEDUPE_MULTIPLE_ACTIVE_CLUSTERS"
MASTER_DATA_DEDUPE_AMBIGUOUS_FIELDS = "MASTER_DATA_DEDUPE_AMBIGUOUS_FIELDS"
MASTER_DATA_DEDUPE_OWNER_SCOPE_MISSING = "MASTER_DATA_DEDUPE_OWNER_SCOPE_MISSING"

POOL_MASTER_DATA_DEDUPE_ACTION_ACCEPT_MERGE = "accept_merge"
POOL_MASTER_DATA_DEDUPE_ACTION_CHOOSE_SURVIVOR = "choose_survivor"
POOL_MASTER_DATA_DEDUPE_ACTION_MARK_DISTINCT = "mark_distinct"

_ACTIVE_CLUSTER_STATUSES = {
    PoolMasterDataDedupeClusterStatus.RESOLVED_AUTO,
    PoolMasterDataDedupeClusterStatus.RESOLVED_MANUAL,
    PoolMasterDataDedupeClusterStatus.PENDING_REVIEW,
}


class MasterDataDedupeReviewRequiredError(RuntimeError):
    def __init__(
        self,
        *,
        detail: str,
        entity_type: str,
        canonical_id: str = "",
        cluster_id: str = "",
        review_item_id: str = "",
        reason_code: str = MASTER_DATA_DEDUPE_REVIEW_REQUIRED,
    ) -> None:
        self.code = MASTER_DATA_DEDUPE_REVIEW_REQUIRED
        self.detail = sanitize_master_data_sync_text(detail) or "Cross-infobase dedupe review is required."
        self.entity_type = str(entity_type or "").strip()
        self.canonical_id = str(canonical_id or "").strip()
        self.cluster_id = str(cluster_id or "").strip()
        self.review_item_id = str(review_item_id or "").strip()
        self.reason_code = str(reason_code or MASTER_DATA_DEDUPE_REVIEW_REQUIRED).strip()
        super().__init__(f"{self.code}: {self.detail}")

    def to_diagnostic(self) -> dict[str, Any]:
        return {
            "error_code": self.code,
            "detail": self.detail,
            "entity_type": self.entity_type,
            "canonical_id": self.canonical_id,
            "dedupe_cluster_id": self.cluster_id,
            "dedupe_review_item_id": self.review_item_id,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True)
class PoolMasterDataDedupeIngestResult:
    action: str
    canonical_id: str
    cluster: PoolMasterDataDedupeCluster
    source_record: PoolMasterDataSourceRecord
    review_item: PoolMasterDataDedupeReviewItem | None
    blocked: bool
    reason_code: str = ""
    detail: str = ""


def supports_pool_master_data_dedupe(*, entity_type: str) -> bool:
    return supports_pool_master_data_capability(
        entity_type=entity_type,
        capability=POOL_MASTER_DATA_CAPABILITY_CROSS_INFOBASE_DEDUPE,
    )


def require_pool_master_data_dedupe_resolved(
    *,
    tenant_id: str,
    entity_type: str,
    canonical_id: str,
) -> None:
    normalized_entity_type = normalize_pool_master_data_entity_type(entity_type)
    normalized_canonical_id = str(canonical_id or "").strip()
    if not normalized_canonical_id or not supports_pool_master_data_dedupe(entity_type=normalized_entity_type):
        return

    cluster = (
        PoolMasterDataDedupeCluster.objects.filter(
            tenant_id=str(tenant_id or "").strip(),
            entity_type=normalized_entity_type,
            canonical_id=normalized_canonical_id,
        )
        .exclude(status=PoolMasterDataDedupeClusterStatus.SUPERSEDED)
        .select_related("review_item")
        .first()
    )
    if cluster is None or cluster.status != PoolMasterDataDedupeClusterStatus.PENDING_REVIEW:
        return

    review_item = getattr(cluster, "review_item", None)
    raise MasterDataDedupeReviewRequiredError(
        detail=(
            f"Canonical {normalized_entity_type} '{normalized_canonical_id}' is blocked by unresolved "
            "cross-infobase dedupe review."
        ),
        entity_type=normalized_entity_type,
        canonical_id=normalized_canonical_id,
        cluster_id=str(cluster.id),
        review_item_id=str(review_item.id) if review_item is not None else "",
        reason_code=str(cluster.reason_code or MASTER_DATA_DEDUPE_REVIEW_REQUIRED),
    )


def ingest_pool_master_data_source_record(
    *,
    tenant_id: str | UUID,
    entity_type: str,
    source_database: Database | None,
    source_ref: str,
    source_canonical_id: str,
    canonical_payload: Mapping[str, Any],
    origin_kind: str,
    origin_ref: str,
    origin_event_id: str,
    metadata: Mapping[str, Any] | None = None,
) -> PoolMasterDataDedupeIngestResult:
    normalized_entity_type = normalize_pool_master_data_entity_type(entity_type)
    if not supports_pool_master_data_dedupe(entity_type=normalized_entity_type):
        raise ValueError(
            f"{MASTER_DATA_DEDUPE_CAPABILITY_DISABLED}: entity_type '{normalized_entity_type}' is not dedupe-capable"
        )

    normalized_source_ref = str(source_ref or "").strip() or str(source_canonical_id or "").strip()
    if not normalized_source_ref:
        raise ValueError("source_ref is required for source-record ingestion")

    payload_snapshot = sanitize_master_data_sync_value(dict(canonical_payload or {}))
    signals = _build_normalized_signals(
        entity_type=normalized_entity_type,
        payload=payload_snapshot,
        source_ref=normalized_source_ref,
    )
    dedupe_key = str(signals.get("dedupe_key") or "").strip()
    fingerprint = _build_source_fingerprint(
        entity_type=normalized_entity_type,
        source_database_id=str(source_database.id) if source_database is not None else "",
        source_ref=normalized_source_ref,
        payload=payload_snapshot,
    )

    with transaction.atomic():
        source_record = _upsert_source_record(
            tenant_id=str(tenant_id),
            entity_type=normalized_entity_type,
            source_database=source_database,
            source_ref=normalized_source_ref,
            source_fingerprint=fingerprint,
            source_canonical_id=source_canonical_id,
            origin_kind=origin_kind,
            origin_ref=origin_ref,
            origin_event_id=origin_event_id,
            normalized_signals=signals,
            payload_snapshot=payload_snapshot,
            metadata=metadata,
        )

        candidate_clusters = _load_candidate_clusters(
            tenant_id=str(tenant_id),
            entity_type=normalized_entity_type,
            dedupe_key=dedupe_key,
            source_record=source_record,
        )

        if len(candidate_clusters) > 1:
            cluster, review_item = _move_cluster_to_pending_review(
                tenant_id=str(tenant_id),
                entity_type=normalized_entity_type,
                cluster=source_record.cluster,
                source_record=source_record,
                reason_code=MASTER_DATA_DEDUPE_MULTIPLE_ACTIVE_CLUSTERS,
                detail="More than one active dedupe cluster matched the same semantic key.",
                conflicting_fields=["dedupe_key"],
                proposed_survivor_source_record=None,
            )
            return PoolMasterDataDedupeIngestResult(
                action="failed",
                canonical_id=str(cluster.canonical_id or ""),
                cluster=cluster,
                source_record=source_record,
                review_item=review_item,
                blocked=True,
                reason_code=MASTER_DATA_DEDUPE_REVIEW_REQUIRED,
                detail="Cross-infobase dedupe review is required.",
            )

        cluster = candidate_clusters[0] if candidate_clusters else None
        if cluster is None:
            cluster = PoolMasterDataDedupeCluster.objects.create(
                tenant_id=str(tenant_id),
                entity_type=normalized_entity_type,
                dedupe_key=dedupe_key,
                status=PoolMasterDataDedupeClusterStatus.RESOLVED_AUTO,
                rollout_eligible=False,
                reason_code="SINGLE_SOURCE",
                reason_detail="Canonical source-of-truth initialized from a single source record.",
                normalized_signals=signals,
                conflicting_fields=[],
                metadata={"origin_kind": origin_kind, "origin_ref": str(origin_ref or "").strip()},
            )

        source_record.cluster = cluster
        source_record.save(update_fields=["cluster", "updated_at"])

        if cluster.status == PoolMasterDataDedupeClusterStatus.PENDING_REVIEW:
            review_item = _ensure_review_item(
                cluster=cluster,
                reason_code=str(cluster.reason_code or MASTER_DATA_DEDUPE_REVIEW_REQUIRED),
                detail=str(cluster.reason_detail or "Cross-infobase dedupe review is required."),
                conflicting_fields=_normalize_conflicting_fields(cluster.conflicting_fields),
                proposed_survivor_source_record=_resolve_proposed_survivor_source_record(cluster=cluster),
            )
            source_record.resolution_status = PoolMasterDataSourceRecordResolutionStatus.PENDING_REVIEW
            source_record.resolution_reason = review_item.reason_code
            source_record.save(update_fields=["resolution_status", "resolution_reason", "updated_at"])
            return PoolMasterDataDedupeIngestResult(
                action="failed",
                canonical_id=str(cluster.canonical_id or ""),
                cluster=cluster,
                source_record=source_record,
                review_item=review_item,
                blocked=True,
                reason_code=MASTER_DATA_DEDUPE_REVIEW_REQUIRED,
                detail="Cross-infobase dedupe review is required.",
            )

        conflict_fields = _detect_conflicting_fields(
            entity_type=normalized_entity_type,
            cluster=cluster,
            source_payload=payload_snapshot,
            source_signals=signals,
        )
        if conflict_fields:
            cluster, review_item = _move_cluster_to_pending_review(
                tenant_id=str(tenant_id),
                entity_type=normalized_entity_type,
                cluster=cluster,
                source_record=source_record,
                reason_code=MASTER_DATA_DEDUPE_AMBIGUOUS_FIELDS,
                detail="Source record conflicts with an existing canonical cluster and requires operator review.",
                conflicting_fields=conflict_fields,
                proposed_survivor_source_record=_resolve_proposed_survivor_source_record(cluster=cluster),
            )
            source_record.resolution_status = PoolMasterDataSourceRecordResolutionStatus.PENDING_REVIEW
            source_record.resolution_reason = review_item.reason_code
            source_record.save(update_fields=["resolution_status", "resolution_reason", "updated_at"])
            return PoolMasterDataDedupeIngestResult(
                action="failed",
                canonical_id=str(cluster.canonical_id or ""),
                cluster=cluster,
                source_record=source_record,
                review_item=review_item,
                blocked=True,
                reason_code=MASTER_DATA_DEDUPE_REVIEW_REQUIRED,
                detail="Cross-infobase dedupe review is required.",
            )

        canonical_id = str(cluster.canonical_id or "").strip() or str(source_canonical_id or "").strip()
        if not canonical_id:
            canonical_id = _build_fallback_canonical_id(
                entity_type=normalized_entity_type,
                source_record_id=str(source_record.id),
            )

        promotion_action = _promote_cluster_to_canonical(
            tenant_id=str(tenant_id),
            entity_type=normalized_entity_type,
            cluster=cluster,
            source_record=source_record,
            canonical_id=canonical_id,
            origin_event_id=origin_event_id,
        )
        cluster = PoolMasterDataDedupeCluster.objects.get(id=cluster.id)
        source_record = PoolMasterDataSourceRecord.objects.get(id=source_record.id)
        review_item = (
            PoolMasterDataDedupeReviewItem.objects.filter(cluster_id=cluster.id).select_related("cluster").first()
        )
        return PoolMasterDataDedupeIngestResult(
            action=promotion_action,
            canonical_id=str(cluster.canonical_id or canonical_id),
            cluster=cluster,
            source_record=source_record,
            review_item=review_item,
            blocked=False,
            reason_code=str(cluster.reason_code or ""),
            detail=str(cluster.reason_detail or ""),
        )


def list_pool_master_data_dedupe_review_items(
    *,
    tenant_id: str,
    status: str | None = None,
    entity_type: str | None = None,
    reason_code: str | None = None,
    cluster_id: str | None = None,
    database_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PoolMasterDataDedupeReviewItem], int]:
    queryset = PoolMasterDataDedupeReviewItem.objects.filter(tenant_id=str(tenant_id or "").strip())
    if status:
        queryset = queryset.filter(status=str(status).strip())
    if entity_type:
        queryset = queryset.filter(entity_type=normalize_pool_master_data_entity_type(entity_type))
    if reason_code:
        queryset = queryset.filter(reason_code=str(reason_code).strip())
    if cluster_id:
        queryset = queryset.filter(cluster_id=str(cluster_id).strip())
    if database_id:
        queryset = queryset.filter(cluster__source_records__source_database_id=str(database_id).strip())
    queryset = queryset.distinct()
    total = queryset.count()
    rows = list(
        queryset.select_related("cluster", "resolved_by", "proposed_survivor_source_record")
        .order_by("-updated_at")[max(0, offset) : max(0, offset) + max(1, limit)]
    )
    return rows, total


def get_pool_master_data_dedupe_review_item(
    *,
    tenant_id: str,
    review_item_id: str,
) -> PoolMasterDataDedupeReviewItem:
    review_item = (
        PoolMasterDataDedupeReviewItem.objects.filter(
            id=str(review_item_id or "").strip(),
            tenant_id=str(tenant_id or "").strip(),
        )
        .select_related("cluster", "resolved_by", "proposed_survivor_source_record")
        .first()
    )
    if review_item is None:
        raise LookupError(
            f"{MASTER_DATA_DEDUPE_REVIEW_ITEM_NOT_FOUND}: review item '{review_item_id}' was not found"
        )
    return review_item


def apply_pool_master_data_dedupe_review_action(
    *,
    tenant_id: str,
    review_item_id: str,
    action: str,
    actor_id: str | UUID | None,
    source_record_id: str | None = None,
    note: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> PoolMasterDataDedupeReviewItem:
    normalized_action = str(action or "").strip().lower()
    if normalized_action not in {
        POOL_MASTER_DATA_DEDUPE_ACTION_ACCEPT_MERGE,
        POOL_MASTER_DATA_DEDUPE_ACTION_CHOOSE_SURVIVOR,
        POOL_MASTER_DATA_DEDUPE_ACTION_MARK_DISTINCT,
    }:
        raise ValueError(
            f"{MASTER_DATA_DEDUPE_INVALID_ACTION}: unsupported dedupe review action '{action}'"
        )

    with transaction.atomic():
        review_item = (
            PoolMasterDataDedupeReviewItem.objects.select_for_update()
            .select_related("cluster")
            .filter(
                id=str(review_item_id or "").strip(),
                tenant_id=str(tenant_id or "").strip(),
            )
            .first()
        )
        if review_item is None:
            raise LookupError(
                f"{MASTER_DATA_DEDUPE_REVIEW_ITEM_NOT_FOUND}: review item '{review_item_id}' was not found"
            )

        cluster = review_item.cluster
        sources = list(
            PoolMasterDataSourceRecord.objects.select_for_update()
            .filter(cluster_id=cluster.id)
            .order_by("created_at", "id")
        )
        if not sources:
            raise ValueError("Review item has no source records to resolve.")

        actor = None
        if actor_id:
            actor = User.objects.filter(id=str(actor_id)).first()

        if normalized_action == POOL_MASTER_DATA_DEDUPE_ACTION_MARK_DISTINCT:
            _resolve_review_item_as_distinct(
                review_item=review_item,
                cluster=cluster,
                sources=sources,
                actor=actor,
                note=note,
                metadata=metadata,
            )
        else:
            selected_source = _resolve_selected_source_record(
                sources=sources,
                source_record_id=source_record_id,
                proposed=review_item.proposed_survivor_source_record,
            )
            _resolve_review_item_as_merge(
                review_item=review_item,
                cluster=cluster,
                sources=sources,
                actor=actor,
                note=note,
                metadata=metadata,
                selected_source=selected_source,
                action=normalized_action,
            )

    return get_pool_master_data_dedupe_review_item(
        tenant_id=str(tenant_id or "").strip(),
        review_item_id=review_item_id,
    )


def serialize_pool_master_data_dedupe_review_item(
    *,
    review_item: PoolMasterDataDedupeReviewItem,
) -> dict[str, Any]:
    cluster = review_item.cluster
    source_records = list(
        PoolMasterDataSourceRecord.objects.filter(cluster_id=cluster.id)
        .select_related("source_database")
        .order_by("created_at", "id")
    )
    return sanitize_master_data_sync_value(
        {
            "id": str(review_item.id),
            "tenant_id": str(review_item.tenant_id),
            "cluster_id": str(review_item.cluster_id),
            "entity_type": str(review_item.entity_type),
            "status": str(review_item.status),
            "reason_code": str(review_item.reason_code),
            "conflicting_fields": _normalize_conflicting_fields(review_item.conflicting_fields),
            "source_snapshot": sanitize_master_data_sync_value(review_item.source_snapshot),
            "proposed_survivor_source_record_id": (
                str(review_item.proposed_survivor_source_record_id)
                if review_item.proposed_survivor_source_record_id
                else None
            ),
            "cluster": {
                "id": str(cluster.id),
                "entity_type": str(cluster.entity_type),
                "canonical_id": str(cluster.canonical_id or ""),
                "dedupe_key": str(cluster.dedupe_key or ""),
                "status": str(cluster.status),
                "rollout_eligible": bool(cluster.rollout_eligible),
                "reason_code": str(cluster.reason_code or ""),
                "reason_detail": sanitize_master_data_sync_text(str(cluster.reason_detail or "")),
                "normalized_signals": sanitize_master_data_sync_value(cluster.normalized_signals),
                "conflicting_fields": _normalize_conflicting_fields(cluster.conflicting_fields),
                "resolved_at": cluster.resolved_at,
                "resolved_by_id": str(cluster.resolved_by_id) if cluster.resolved_by_id else None,
            },
            "source_records": [serialize_pool_master_data_source_record(source_record=item) for item in source_records],
            "resolved_at": review_item.resolved_at,
            "resolved_by_id": str(review_item.resolved_by_id) if review_item.resolved_by_id else None,
            "resolved_by_username": review_item.resolved_by.username if review_item.resolved_by else "",
            "created_at": review_item.created_at,
            "updated_at": review_item.updated_at,
            "metadata": sanitize_master_data_sync_value(review_item.metadata),
        }
    )


def serialize_pool_master_data_source_record(
    *,
    source_record: PoolMasterDataSourceRecord,
) -> dict[str, Any]:
    source_database = source_record.source_database
    return sanitize_master_data_sync_value(
        {
            "id": str(source_record.id),
            "tenant_id": str(source_record.tenant_id),
            "entity_type": str(source_record.entity_type),
            "cluster_id": str(source_record.cluster_id) if source_record.cluster_id else None,
            "source_database_id": str(source_database.id) if source_database is not None else None,
            "source_database_name": str(source_database.name) if source_database is not None else "",
            "source_ref": str(source_record.source_ref),
            "source_fingerprint": str(source_record.source_fingerprint or ""),
            "source_canonical_id": str(source_record.source_canonical_id or ""),
            "canonical_id": str(source_record.canonical_id or ""),
            "origin_kind": str(source_record.origin_kind or ""),
            "origin_ref": str(source_record.origin_ref or ""),
            "resolution_status": str(source_record.resolution_status),
            "resolution_reason": str(source_record.resolution_reason or ""),
            "normalized_signals": sanitize_master_data_sync_value(source_record.normalized_signals),
            "payload_snapshot": sanitize_master_data_sync_value(source_record.payload_snapshot),
            "metadata": sanitize_master_data_sync_value(source_record.metadata),
            "created_at": source_record.created_at,
            "updated_at": source_record.updated_at,
        }
    )


def _upsert_source_record(
    *,
    tenant_id: str,
    entity_type: str,
    source_database: Database | None,
    source_ref: str,
    source_fingerprint: str,
    source_canonical_id: str,
    origin_kind: str,
    origin_ref: str,
    origin_event_id: str,
    normalized_signals: Mapping[str, Any],
    payload_snapshot: Mapping[str, Any],
    metadata: Mapping[str, Any] | None,
) -> PoolMasterDataSourceRecord:
    queryset = PoolMasterDataSourceRecord.objects.select_for_update().filter(
        tenant_id=str(tenant_id or "").strip(),
        entity_type=str(entity_type or "").strip(),
        source_ref=str(source_ref or "").strip(),
    )
    if source_database is not None:
        queryset = queryset.filter(source_database=source_database)
    else:
        queryset = queryset.filter(source_database__isnull=True)
    source_record = queryset.first()
    payload = {
        "tenant_id": str(tenant_id or "").strip(),
        "entity_type": str(entity_type or "").strip(),
        "source_database": source_database,
        "source_ref": str(source_ref or "").strip(),
        "source_fingerprint": str(source_fingerprint or "").strip(),
        "source_canonical_id": str(source_canonical_id or "").strip(),
        "origin_kind": str(origin_kind or "").strip(),
        "origin_ref": str(origin_ref or "").strip(),
        "normalized_signals": sanitize_master_data_sync_value(dict(normalized_signals or {})),
        "payload_snapshot": sanitize_master_data_sync_value(dict(payload_snapshot or {})),
        "metadata": sanitize_master_data_sync_value(
            {
                **dict(metadata or {}),
                "origin_event_id": str(origin_event_id or "").strip(),
            }
        ),
    }
    if source_record is None:
        return PoolMasterDataSourceRecord.objects.create(**payload)

    for field_name, value in payload.items():
        setattr(source_record, field_name, value)
    source_record.save()
    return source_record


def _load_candidate_clusters(
    *,
    tenant_id: str,
    entity_type: str,
    dedupe_key: str,
    source_record: PoolMasterDataSourceRecord,
) -> list[PoolMasterDataDedupeCluster]:
    if source_record.cluster_id:
        cluster = (
            PoolMasterDataDedupeCluster.objects.select_for_update()
            .filter(id=source_record.cluster_id)
            .first()
        )
        if cluster is not None and cluster.status in _ACTIVE_CLUSTER_STATUSES:
            return [cluster]

    filters = Q(tenant_id=str(tenant_id or "").strip(), entity_type=str(entity_type or "").strip())
    filters &= Q(status__in=_ACTIVE_CLUSTER_STATUSES)
    if dedupe_key:
        filters &= Q(dedupe_key=dedupe_key)
    else:
        filters &= Q(id__in=[])
    return list(PoolMasterDataDedupeCluster.objects.select_for_update().filter(filters).order_by("created_at", "id"))


def _build_normalized_signals(
    *,
    entity_type: str,
    payload: Mapping[str, Any],
    source_ref: str,
) -> dict[str, Any]:
    normalized_entity_type = normalize_pool_master_data_entity_type(entity_type)
    if normalized_entity_type == PoolMasterDataEntityType.PARTY:
        inn = _digits_only(payload.get("inn"))
        kpp = _digits_only(payload.get("kpp"))
        name = _normalize_text_token(payload.get("name"))
        roles = {
            "organization": bool(payload.get("is_our_organization")),
            "counterparty": bool(payload.get("is_counterparty", True)),
        }
        dedupe_key = f"party:{inn}:{kpp or '_'}" if inn else f"party:source:{source_ref}"
        return {
            "dedupe_key": dedupe_key,
            "inn": inn,
            "kpp": kpp,
            "name": name,
            "roles": roles,
        }
    if normalized_entity_type == PoolMasterDataEntityType.ITEM:
        sku = _normalize_text_token(payload.get("sku"))
        unit = _normalize_text_token(payload.get("unit"))
        name = _normalize_text_token(payload.get("name"))
        if sku:
            dedupe_key = f"item:sku:{sku}"
        elif name and unit:
            dedupe_key = f"item:name:{name}:unit:{unit}"
        else:
            dedupe_key = f"item:source:{source_ref}"
        return {
            "dedupe_key": dedupe_key,
            "sku": sku,
            "unit": unit,
            "name": name,
        }
    if normalized_entity_type == PoolMasterDataEntityType.TAX_PROFILE:
        vat_code = _normalize_text_token(payload.get("vat_code"))
        vat_rate = _normalize_decimal_token(payload.get("vat_rate"))
        vat_included = bool(payload.get("vat_included"))
        dedupe_key = f"tax:{vat_code}:{vat_rate}:{int(vat_included)}"
        return {
            "dedupe_key": dedupe_key,
            "vat_code": vat_code,
            "vat_rate": vat_rate,
            "vat_included": vat_included,
        }
    if normalized_entity_type == PoolMasterDataEntityType.GL_ACCOUNT:
        chart_identity = _normalize_text_token(payload.get("chart_identity"))
        code = _normalize_text_token(payload.get("code"))
        name = _normalize_text_token(payload.get("name"))
        dedupe_key = (
            f"gl_account:{chart_identity}:{code}"
            if chart_identity and code
            else f"gl_account:source:{source_ref}"
        )
        return {
            "dedupe_key": dedupe_key,
            "chart_identity": chart_identity,
            "code": code,
            "name": name,
        }
    if normalized_entity_type == PoolMasterDataEntityType.CONTRACT:
        owner_counterparty_canonical_id = _normalize_text_token(payload.get("owner_counterparty_canonical_id"))
        number = _normalize_text_token(payload.get("number"))
        date_token = _normalize_date_token(payload.get("date"))
        name = _normalize_text_token(payload.get("name"))
        if owner_counterparty_canonical_id and (number or date_token):
            dedupe_key = f"contract:{owner_counterparty_canonical_id}:{number or '_'}:{date_token or '_'}"
        else:
            dedupe_key = f"contract:source:{source_ref}"
        return {
            "dedupe_key": dedupe_key,
            "owner_counterparty_canonical_id": owner_counterparty_canonical_id,
            "number": number,
            "date": date_token,
            "name": name,
        }
    raise ValueError(f"Unsupported dedupe entity_type '{entity_type}'")


def _detect_conflicting_fields(
    *,
    entity_type: str,
    cluster: PoolMasterDataDedupeCluster,
    source_payload: Mapping[str, Any],
    source_signals: Mapping[str, Any],
) -> list[str]:
    existing_sources = list(cluster.source_records.all().order_by("created_at", "id"))
    if not existing_sources:
        return []

    normalized_entity_type = normalize_pool_master_data_entity_type(entity_type)
    conflicts: list[str] = []
    for existing in existing_sources:
        existing_signals = existing.normalized_signals if isinstance(existing.normalized_signals, dict) else {}
        existing_payload = existing.payload_snapshot if isinstance(existing.payload_snapshot, dict) else {}
        if normalized_entity_type == PoolMasterDataEntityType.PARTY:
            if existing_signals.get("inn") and source_signals.get("inn") and existing_signals.get("inn") != source_signals.get("inn"):
                conflicts.append("inn")
            if existing_signals.get("kpp") and source_signals.get("kpp") and existing_signals.get("kpp") != source_signals.get("kpp"):
                conflicts.append("kpp")
            if existing_signals.get("name") and source_signals.get("name") and existing_signals.get("name") != source_signals.get("name"):
                conflicts.append("name")
        elif normalized_entity_type == PoolMasterDataEntityType.ITEM:
            if existing_signals.get("sku") and source_signals.get("sku") and existing_signals.get("sku") != source_signals.get("sku"):
                conflicts.append("sku")
            if existing_signals.get("unit") and source_signals.get("unit") and existing_signals.get("unit") != source_signals.get("unit"):
                conflicts.append("unit")
            if existing_signals.get("name") and source_signals.get("name") and existing_signals.get("name") != source_signals.get("name"):
                conflicts.append("name")
        elif normalized_entity_type == PoolMasterDataEntityType.TAX_PROFILE:
            if existing_signals != source_signals:
                conflicts.extend(["vat_code", "vat_rate", "vat_included"])
        elif normalized_entity_type == PoolMasterDataEntityType.GL_ACCOUNT:
            if existing_signals.get("chart_identity") != source_signals.get("chart_identity"):
                conflicts.append("chart_identity")
            if existing_signals.get("code") != source_signals.get("code"):
                conflicts.append("code")
            if existing_payload.get("name") and source_payload.get("name") and _normalize_text_token(existing_payload.get("name")) != _normalize_text_token(source_payload.get("name")):
                conflicts.append("name")
        elif normalized_entity_type == PoolMasterDataEntityType.CONTRACT:
            if not source_signals.get("owner_counterparty_canonical_id"):
                conflicts.append("owner_counterparty_canonical_id")
            if existing_signals.get("owner_counterparty_canonical_id") and source_signals.get("owner_counterparty_canonical_id") and existing_signals.get("owner_counterparty_canonical_id") != source_signals.get("owner_counterparty_canonical_id"):
                conflicts.append("owner_counterparty_canonical_id")
            if existing_signals.get("number") and source_signals.get("number") and existing_signals.get("number") != source_signals.get("number"):
                conflicts.append("number")
            if existing_signals.get("date") and source_signals.get("date") and existing_signals.get("date") != source_signals.get("date"):
                conflicts.append("date")
            if existing_signals.get("name") and source_signals.get("name") and existing_signals.get("name") != source_signals.get("name"):
                conflicts.append("name")
    return sorted(set(str(item) for item in conflicts if str(item).strip()))


def _move_cluster_to_pending_review(
    *,
    tenant_id: str,
    entity_type: str,
    cluster: PoolMasterDataDedupeCluster | None,
    source_record: PoolMasterDataSourceRecord,
    reason_code: str,
    detail: str,
    conflicting_fields: list[str],
    proposed_survivor_source_record: PoolMasterDataSourceRecord | None,
) -> tuple[PoolMasterDataDedupeCluster, PoolMasterDataDedupeReviewItem]:
    if cluster is None:
        cluster = PoolMasterDataDedupeCluster.objects.create(
            tenant_id=str(tenant_id or "").strip(),
            entity_type=str(entity_type or "").strip(),
            dedupe_key=str(source_record.normalized_signals.get("dedupe_key") or ""),
            status=PoolMasterDataDedupeClusterStatus.PENDING_REVIEW,
            rollout_eligible=False,
            reason_code=str(reason_code or MASTER_DATA_DEDUPE_REVIEW_REQUIRED),
            reason_detail=sanitize_master_data_sync_text(detail),
            normalized_signals=sanitize_master_data_sync_value(source_record.normalized_signals),
            conflicting_fields=_normalize_conflicting_fields(conflicting_fields),
            metadata={},
        )
        source_record.cluster = cluster
        source_record.save(update_fields=["cluster", "updated_at"])
    else:
        cluster.status = PoolMasterDataDedupeClusterStatus.PENDING_REVIEW
        cluster.rollout_eligible = False
        cluster.reason_code = str(reason_code or MASTER_DATA_DEDUPE_REVIEW_REQUIRED)
        cluster.reason_detail = sanitize_master_data_sync_text(detail)
        cluster.conflicting_fields = _normalize_conflicting_fields(conflicting_fields)
        cluster.save(
            update_fields=[
                "status",
                "rollout_eligible",
                "reason_code",
                "reason_detail",
                "conflicting_fields",
                "updated_at",
            ]
        )
    review_item = _ensure_review_item(
        cluster=cluster,
        reason_code=str(reason_code or MASTER_DATA_DEDUPE_REVIEW_REQUIRED),
        detail=detail,
        conflicting_fields=conflicting_fields,
        proposed_survivor_source_record=proposed_survivor_source_record,
    )
    return cluster, review_item


def _ensure_review_item(
    *,
    cluster: PoolMasterDataDedupeCluster,
    reason_code: str,
    detail: str,
    conflicting_fields: list[str],
    proposed_survivor_source_record: PoolMasterDataSourceRecord | None,
) -> PoolMasterDataDedupeReviewItem:
    source_snapshot = [
        serialize_pool_master_data_source_record(source_record=item)
        for item in cluster.source_records.select_related("source_database").order_by("created_at", "id")
    ]
    review_item, created = PoolMasterDataDedupeReviewItem.objects.get_or_create(
        cluster=cluster,
        defaults={
            "tenant_id": str(cluster.tenant_id),
            "entity_type": str(cluster.entity_type),
            "status": PoolMasterDataDedupeReviewStatus.PENDING,
            "reason_code": str(reason_code or MASTER_DATA_DEDUPE_REVIEW_REQUIRED),
            "conflicting_fields": _normalize_conflicting_fields(conflicting_fields),
            "source_snapshot": source_snapshot,
            "proposed_survivor_source_record": proposed_survivor_source_record,
            "metadata": {"detail": sanitize_master_data_sync_text(detail)},
        },
    )
    if created:
        return review_item
    review_item.status = PoolMasterDataDedupeReviewStatus.PENDING
    review_item.reason_code = str(reason_code or MASTER_DATA_DEDUPE_REVIEW_REQUIRED)
    review_item.conflicting_fields = _normalize_conflicting_fields(conflicting_fields)
    review_item.source_snapshot = source_snapshot
    review_item.proposed_survivor_source_record = proposed_survivor_source_record
    review_item.metadata = {
        **dict(review_item.metadata or {}),
        "detail": sanitize_master_data_sync_text(detail),
    }
    review_item.save(
        update_fields=[
            "status",
            "reason_code",
            "conflicting_fields",
            "source_snapshot",
            "proposed_survivor_source_record",
            "metadata",
            "updated_at",
        ]
    )
    return review_item


def _resolve_proposed_survivor_source_record(
    *,
    cluster: PoolMasterDataDedupeCluster,
) -> PoolMasterDataSourceRecord | None:
    if cluster.canonical_id:
        matched = cluster.source_records.filter(canonical_id=str(cluster.canonical_id)).order_by("created_at").first()
        if matched is not None:
            return matched
    return cluster.source_records.order_by("created_at", "id").first()


def _promote_cluster_to_canonical(
    *,
    tenant_id: str,
    entity_type: str,
    cluster: PoolMasterDataDedupeCluster,
    source_record: PoolMasterDataSourceRecord,
    canonical_id: str,
    origin_event_id: str,
) -> str:
    existing_sources = list(cluster.source_records.exclude(id=source_record.id).order_by("created_at", "id"))
    base_payload: dict[str, Any]
    if cluster.canonical_id:
        existing_entity = _get_existing_canonical_entity(
            tenant_id=tenant_id,
            entity_type=entity_type,
            canonical_id=str(cluster.canonical_id),
        )
        if existing_entity is not None:
            base_payload = _serialize_existing_canonical_entity(entity_type=entity_type, entity=existing_entity)
        elif existing_sources:
            base_payload = dict(existing_sources[0].payload_snapshot or {})
        else:
            base_payload = {}
    elif existing_sources:
        base_payload = dict(existing_sources[0].payload_snapshot or {})
    else:
        base_payload = {}

    merged_payload = _merge_entity_payloads(
        entity_type=entity_type,
        base_payload=base_payload,
        incoming_payload=source_record.payload_snapshot if isinstance(source_record.payload_snapshot, dict) else {},
    )
    upsert_result = _promote_canonical_entity(
        tenant_id=tenant_id,
        entity_type=entity_type,
        canonical_id=canonical_id,
        payload=merged_payload,
        origin_event_id=origin_event_id,
    )
    resolved_status = (
        PoolMasterDataSourceRecordResolutionStatus.RESOLVED_AUTO
    )
    cluster.canonical_id = canonical_id
    cluster.status = PoolMasterDataDedupeClusterStatus.RESOLVED_AUTO
    cluster.rollout_eligible = bool(_get_rollout_eligible(entity_type=entity_type))
    cluster.reason_code = "SAFE_AUTO_RESOLUTION"
    cluster.reason_detail = "Cross-infobase source record was auto-resolved into canonical source-of-truth."
    cluster.normalized_signals = sanitize_master_data_sync_value(source_record.normalized_signals)
    cluster.conflicting_fields = []
    cluster.resolved_at = timezone.now()
    cluster.save(
        update_fields=[
            "canonical_id",
            "status",
            "rollout_eligible",
            "reason_code",
            "reason_detail",
            "normalized_signals",
            "conflicting_fields",
            "resolved_at",
            "updated_at",
        ]
    )
    cluster.source_records.update(
        canonical_id=canonical_id,
        resolution_status=resolved_status,
        resolution_reason=cluster.reason_code,
        updated_at=timezone.now(),
    )
    if hasattr(cluster, "review_item"):
        review_item = cluster.review_item
        review_item.status = PoolMasterDataDedupeReviewStatus.RESOLVED_AUTO
        review_item.resolved_at = timezone.now()
        review_item.save(update_fields=["status", "resolved_at", "updated_at"])
    if upsert_result.created:
        return "created"
    if upsert_result.changed:
        return "updated"
    return "skipped"


def _resolve_review_item_as_merge(
    *,
    review_item: PoolMasterDataDedupeReviewItem,
    cluster: PoolMasterDataDedupeCluster,
    sources: list[PoolMasterDataSourceRecord],
    actor: User | None,
    note: str,
    metadata: Mapping[str, Any] | None,
    selected_source: PoolMasterDataSourceRecord,
    action: str,
) -> None:
    canonical_id = str(cluster.canonical_id or "").strip() or str(selected_source.source_canonical_id or "").strip()
    if not canonical_id:
        canonical_id = _build_fallback_canonical_id(
            entity_type=str(cluster.entity_type),
            source_record_id=str(selected_source.id),
        )
    merged_payload: dict[str, Any] = {}
    for source in sources:
        merged_payload = _merge_entity_payloads(
            entity_type=str(cluster.entity_type),
            base_payload=merged_payload,
            incoming_payload=source.payload_snapshot if isinstance(source.payload_snapshot, dict) else {},
        )
    merged_payload = _merge_entity_payloads(
        entity_type=str(cluster.entity_type),
        base_payload=merged_payload,
        incoming_payload=selected_source.payload_snapshot if isinstance(selected_source.payload_snapshot, dict) else {},
    )
    _promote_canonical_entity(
        tenant_id=str(cluster.tenant_id),
        entity_type=str(cluster.entity_type),
        canonical_id=canonical_id,
        payload=merged_payload,
        origin_event_id=f"dedupe-review:{review_item.id}:{action}",
    )
    now = timezone.now()
    cluster.canonical_id = canonical_id
    cluster.status = PoolMasterDataDedupeClusterStatus.RESOLVED_MANUAL
    cluster.rollout_eligible = bool(_get_rollout_eligible(entity_type=str(cluster.entity_type)))
    cluster.reason_code = action.upper()
    cluster.reason_detail = sanitize_master_data_sync_text(note) or "Cluster was resolved by operator."
    cluster.conflicting_fields = []
    cluster.resolved_at = now
    cluster.resolved_by = actor
    cluster.metadata = {
        **dict(cluster.metadata or {}),
        "resolution_action": action,
        "resolution_note": sanitize_master_data_sync_text(note),
        "resolution_metadata": sanitize_master_data_sync_value(dict(metadata or {})),
    }
    cluster.save(
        update_fields=[
            "canonical_id",
            "status",
            "rollout_eligible",
            "reason_code",
            "reason_detail",
            "conflicting_fields",
            "resolved_at",
            "resolved_by",
            "metadata",
            "updated_at",
        ]
    )
    for source in sources:
        source.canonical_id = canonical_id
        source.resolution_status = PoolMasterDataSourceRecordResolutionStatus.RESOLVED_MANUAL
        source.resolution_reason = action.upper()
        source.save(update_fields=["canonical_id", "resolution_status", "resolution_reason", "updated_at"])
    review_item.status = PoolMasterDataDedupeReviewStatus.RESOLVED_MANUAL
    review_item.proposed_survivor_source_record = selected_source
    review_item.source_snapshot = [
        serialize_pool_master_data_source_record(source_record=item) for item in sources
    ]
    review_item.resolved_at = now
    review_item.resolved_by = actor
    review_item.metadata = {
        **dict(review_item.metadata or {}),
        "resolution_action": action,
        "resolution_note": sanitize_master_data_sync_text(note),
        "resolution_metadata": sanitize_master_data_sync_value(dict(metadata or {})),
    }
    review_item.save(
        update_fields=[
            "status",
            "proposed_survivor_source_record",
            "source_snapshot",
            "resolved_at",
            "resolved_by",
            "metadata",
            "updated_at",
        ]
    )


def _resolve_review_item_as_distinct(
    *,
    review_item: PoolMasterDataDedupeReviewItem,
    cluster: PoolMasterDataDedupeCluster,
    sources: list[PoolMasterDataSourceRecord],
    actor: User | None,
    note: str,
    metadata: Mapping[str, Any] | None,
) -> None:
    now = timezone.now()
    split_cluster_ids: list[str] = []
    retained_canonical_id = str(cluster.canonical_id or "").strip()
    cluster.status = PoolMasterDataDedupeClusterStatus.SUPERSEDED
    cluster.canonical_id = None
    cluster.rollout_eligible = False
    cluster.reason_code = "MANUAL_MARK_DISTINCT"
    cluster.reason_detail = sanitize_master_data_sync_text(note) or "Operator marked cluster as distinct."
    cluster.resolved_at = now
    cluster.resolved_by = actor
    cluster.metadata = {
        **dict(cluster.metadata or {}),
        "resolution_action": POOL_MASTER_DATA_DEDUPE_ACTION_MARK_DISTINCT,
        "superseded_canonical_id": retained_canonical_id,
        "resolution_note": sanitize_master_data_sync_text(note),
        "resolution_metadata": sanitize_master_data_sync_value(dict(metadata or {})),
    }
    cluster.save(
        update_fields=[
            "status",
            "canonical_id",
            "rollout_eligible",
            "reason_code",
            "reason_detail",
            "resolved_at",
            "resolved_by",
            "metadata",
            "updated_at",
        ]
    )
    for index, source in enumerate(sources):
        canonical_id = (
            retained_canonical_id
            if index == 0 and retained_canonical_id
            else str(source.source_canonical_id or "").strip()
        )
        if not canonical_id:
            canonical_id = _build_fallback_canonical_id(
                entity_type=str(cluster.entity_type),
                source_record_id=str(source.id),
            )
        new_cluster = PoolMasterDataDedupeCluster.objects.create(
            tenant_id=str(cluster.tenant_id),
            entity_type=str(cluster.entity_type),
            dedupe_key=f"distinct:{cluster.id}:{source.id}",
            canonical_id=canonical_id,
            status=PoolMasterDataDedupeClusterStatus.RESOLVED_MANUAL,
            rollout_eligible=bool(_get_rollout_eligible(entity_type=str(cluster.entity_type))),
            reason_code="MANUAL_MARK_DISTINCT",
            reason_detail="Operator marked source records as distinct business entities.",
            normalized_signals=sanitize_master_data_sync_value(source.normalized_signals),
            conflicting_fields=[],
            metadata={"origin_cluster_id": str(cluster.id)},
            resolved_at=now,
            resolved_by=actor,
        )
        _promote_canonical_entity(
            tenant_id=str(cluster.tenant_id),
            entity_type=str(cluster.entity_type),
            canonical_id=canonical_id,
            payload=source.payload_snapshot if isinstance(source.payload_snapshot, dict) else {},
            origin_event_id=f"dedupe-review:{review_item.id}:mark_distinct:{source.id}",
        )
        source.cluster = new_cluster
        source.canonical_id = canonical_id
        source.resolution_status = PoolMasterDataSourceRecordResolutionStatus.RESOLVED_MANUAL
        source.resolution_reason = "MANUAL_MARK_DISTINCT"
        source.save(update_fields=["cluster", "canonical_id", "resolution_status", "resolution_reason", "updated_at"])
        split_cluster_ids.append(str(new_cluster.id))

    cluster.metadata = {
        **dict(cluster.metadata or {}),
        "split_cluster_ids": split_cluster_ids,
    }
    cluster.save(
        update_fields=[
            "metadata",
            "updated_at",
        ]
    )
    review_item.status = PoolMasterDataDedupeReviewStatus.RESOLVED_MANUAL
    review_item.resolved_at = now
    review_item.resolved_by = actor
    review_item.source_snapshot = [
        serialize_pool_master_data_source_record(source_record=item)
        for item in PoolMasterDataSourceRecord.objects.filter(id__in=[source.id for source in sources]).order_by("created_at", "id")
    ]
    review_item.metadata = {
        **dict(review_item.metadata or {}),
        "resolution_action": POOL_MASTER_DATA_DEDUPE_ACTION_MARK_DISTINCT,
        "split_cluster_ids": split_cluster_ids,
        "resolution_note": sanitize_master_data_sync_text(note),
        "resolution_metadata": sanitize_master_data_sync_value(dict(metadata or {})),
    }
    review_item.save(
        update_fields=["status", "resolved_at", "resolved_by", "source_snapshot", "metadata", "updated_at"]
    )


def _resolve_selected_source_record(
    *,
    sources: list[PoolMasterDataSourceRecord],
    source_record_id: str | None,
    proposed: PoolMasterDataSourceRecord | None,
) -> PoolMasterDataSourceRecord:
    if source_record_id:
        for item in sources:
            if str(item.id) == str(source_record_id):
                return item
    if proposed is not None:
        for item in sources:
            if item.id == proposed.id:
                return item
    return sources[0]


def _promote_canonical_entity(
    *,
    tenant_id: str,
    entity_type: str,
    canonical_id: str,
    payload: Mapping[str, Any],
    origin_event_id: str,
):
    from .master_data_canonical_upsert import (
        upsert_pool_master_data_contract,
        upsert_pool_master_data_gl_account,
        upsert_pool_master_data_item,
        upsert_pool_master_data_party,
        upsert_pool_master_data_tax_profile,
    )

    normalized_entity_type = normalize_pool_master_data_entity_type(entity_type)
    existing = _get_existing_canonical_entity(
        tenant_id=tenant_id,
        entity_type=normalized_entity_type,
        canonical_id=canonical_id,
    )

    if normalized_entity_type == PoolMasterDataEntityType.PARTY:
        return upsert_pool_master_data_party(
            tenant_id=tenant_id,
            canonical_id=canonical_id,
            name=str(payload.get("name") or ""),
            full_name=str(payload.get("full_name") or ""),
            inn=str(payload.get("inn") or ""),
            kpp=str(payload.get("kpp") or ""),
            is_our_organization=bool(payload.get("is_our_organization")),
            is_counterparty=bool(payload.get("is_counterparty", True)),
            metadata=dict(payload.get("metadata") or {}),
            existing=existing,
            origin_system="ib",
            origin_event_id=origin_event_id,
        )
    if normalized_entity_type == PoolMasterDataEntityType.ITEM:
        return upsert_pool_master_data_item(
            tenant_id=tenant_id,
            canonical_id=canonical_id,
            name=str(payload.get("name") or ""),
            sku=str(payload.get("sku") or ""),
            unit=str(payload.get("unit") or ""),
            metadata=dict(payload.get("metadata") or {}),
            existing=existing,
            origin_system="ib",
            origin_event_id=origin_event_id,
        )
    if normalized_entity_type == PoolMasterDataEntityType.TAX_PROFILE:
        return upsert_pool_master_data_tax_profile(
            tenant_id=tenant_id,
            canonical_id=canonical_id,
            vat_rate=Decimal(str(payload.get("vat_rate") or "0")),
            vat_included=bool(payload.get("vat_included", True)),
            vat_code=str(payload.get("vat_code") or ""),
            metadata=dict(payload.get("metadata") or {}),
            existing=existing,
            origin_system="ib",
            origin_event_id=origin_event_id,
        )
    if normalized_entity_type == PoolMasterDataEntityType.GL_ACCOUNT:
        return upsert_pool_master_data_gl_account(
            tenant_id=tenant_id,
            canonical_id=canonical_id,
            code=str(payload.get("code") or ""),
            name=str(payload.get("name") or ""),
            chart_identity=str(payload.get("chart_identity") or ""),
            config_name=str(payload.get("config_name") or ""),
            config_version=str(payload.get("config_version") or ""),
            metadata=dict(payload.get("metadata") or {}),
            existing=existing,
            origin_system="ib",
            origin_event_id=origin_event_id,
        )
    if normalized_entity_type == PoolMasterDataEntityType.CONTRACT:
        owner_counterparty_canonical_id = str(payload.get("owner_counterparty_canonical_id") or "").strip()
        owner_counterparty = PoolMasterParty.objects.filter(
            tenant_id=str(tenant_id),
            canonical_id=owner_counterparty_canonical_id,
        ).first()
        if owner_counterparty is None:
            raise MasterDataDedupeReviewRequiredError(
                detail=(
                    f"Contract canonical promotion requires resolved owner counterparty "
                    f"'{owner_counterparty_canonical_id}'."
                ),
                entity_type=normalized_entity_type,
                canonical_id=canonical_id,
                reason_code=MASTER_DATA_DEDUPE_OWNER_SCOPE_MISSING,
            )
        return upsert_pool_master_data_contract(
            tenant_id=tenant_id,
            canonical_id=canonical_id,
            name=str(payload.get("name") or ""),
            owner_counterparty=owner_counterparty,
            number=str(payload.get("number") or ""),
            date=payload.get("date"),
            metadata=dict(payload.get("metadata") or {}),
            existing=existing,
            origin_system="ib",
            origin_event_id=origin_event_id,
        )
    raise ValueError(f"Unsupported canonical promotion entity_type '{entity_type}'")


def _merge_entity_payloads(
    *,
    entity_type: str,
    base_payload: Mapping[str, Any],
    incoming_payload: Mapping[str, Any],
) -> dict[str, Any]:
    merged = dict(base_payload or {})
    incoming = dict(incoming_payload or {})
    if not merged:
        return incoming

    if entity_type == PoolMasterDataEntityType.PARTY:
        for field_name in ("name", "full_name", "inn", "kpp"):
            if not str(merged.get(field_name) or "").strip() and str(incoming.get(field_name) or "").strip():
                merged[field_name] = incoming.get(field_name)
        merged["is_our_organization"] = bool(merged.get("is_our_organization")) or bool(
            incoming.get("is_our_organization")
        )
        merged["is_counterparty"] = bool(merged.get("is_counterparty", True)) or bool(
            incoming.get("is_counterparty", True)
        )
    elif entity_type == PoolMasterDataEntityType.ITEM:
        for field_name in ("name", "sku", "unit"):
            if not str(merged.get(field_name) or "").strip() and str(incoming.get(field_name) or "").strip():
                merged[field_name] = incoming.get(field_name)
    elif entity_type == PoolMasterDataEntityType.TAX_PROFILE:
        for field_name in ("vat_rate", "vat_included", "vat_code"):
            if merged.get(field_name) in (None, "") and incoming.get(field_name) not in (None, ""):
                merged[field_name] = incoming.get(field_name)
    elif entity_type == PoolMasterDataEntityType.GL_ACCOUNT:
        for field_name in ("code", "name", "chart_identity", "config_name", "config_version"):
            if not str(merged.get(field_name) or "").strip() and str(incoming.get(field_name) or "").strip():
                merged[field_name] = incoming.get(field_name)
    elif entity_type == PoolMasterDataEntityType.CONTRACT:
        for field_name in ("name", "number", "owner_counterparty_canonical_id"):
            if not str(merged.get(field_name) or "").strip() and str(incoming.get(field_name) or "").strip():
                merged[field_name] = incoming.get(field_name)
        if merged.get("date") in (None, "") and incoming.get("date") not in (None, ""):
            merged["date"] = incoming.get("date")
    merged["metadata"] = sanitize_master_data_sync_value(
        {
            **dict(merged.get("metadata") or {}),
            **dict(incoming.get("metadata") or {}),
        }
    )
    return merged


def _get_existing_canonical_entity(
    *,
    tenant_id: str,
    entity_type: str,
    canonical_id: str,
):
    normalized_entity_type = normalize_pool_master_data_entity_type(entity_type)
    filters = {"tenant_id": str(tenant_id or "").strip(), "canonical_id": str(canonical_id or "").strip()}
    if normalized_entity_type == PoolMasterDataEntityType.PARTY:
        return PoolMasterParty.objects.filter(**filters).first()
    if normalized_entity_type == PoolMasterDataEntityType.ITEM:
        return PoolMasterItem.objects.filter(**filters).first()
    if normalized_entity_type == PoolMasterDataEntityType.TAX_PROFILE:
        return PoolMasterTaxProfile.objects.filter(**filters).first()
    if normalized_entity_type == PoolMasterDataEntityType.GL_ACCOUNT:
        return PoolMasterGLAccount.objects.filter(**filters).first()
    if normalized_entity_type == PoolMasterDataEntityType.CONTRACT:
        return PoolMasterContract.objects.filter(**filters).first()
    return None


def _serialize_existing_canonical_entity(*, entity_type: str, entity: object) -> dict[str, Any]:
    normalized_entity_type = normalize_pool_master_data_entity_type(entity_type)
    if normalized_entity_type == PoolMasterDataEntityType.PARTY:
        party = entity
        return {
            "name": party.name,
            "full_name": party.full_name,
            "inn": party.inn,
            "kpp": party.kpp,
            "is_our_organization": bool(party.is_our_organization),
            "is_counterparty": bool(party.is_counterparty),
            "metadata": dict(party.metadata or {}),
        }
    if normalized_entity_type == PoolMasterDataEntityType.ITEM:
        item = entity
        return {
            "name": item.name,
            "sku": item.sku,
            "unit": item.unit,
            "metadata": dict(item.metadata or {}),
        }
    if normalized_entity_type == PoolMasterDataEntityType.TAX_PROFILE:
        tax_profile = entity
        return {
            "vat_rate": tax_profile.vat_rate,
            "vat_included": bool(tax_profile.vat_included),
            "vat_code": tax_profile.vat_code,
            "metadata": dict(tax_profile.metadata or {}),
        }
    if normalized_entity_type == PoolMasterDataEntityType.GL_ACCOUNT:
        gl_account = entity
        return {
            "code": gl_account.code,
            "name": gl_account.name,
            "chart_identity": gl_account.chart_identity,
            "config_name": gl_account.config_name,
            "config_version": gl_account.config_version,
            "metadata": dict(gl_account.metadata or {}),
        }
    if normalized_entity_type == PoolMasterDataEntityType.CONTRACT:
        contract = entity
        return {
            "name": contract.name,
            "owner_counterparty_canonical_id": str(contract.owner_counterparty.canonical_id),
            "number": contract.number,
            "date": contract.date,
            "metadata": dict(contract.metadata or {}),
        }
    raise ValueError(f"Unsupported entity_type '{entity_type}'")


def _get_rollout_eligible(*, entity_type: str) -> bool:
    entry = get_pool_master_data_registry_entry(entity_type)
    if entry is None:
        return False
    return bool(entry.dedupe_contract.rollout_eligible)


def _build_source_fingerprint(
    *,
    entity_type: str,
    source_database_id: str,
    source_ref: str,
    payload: Mapping[str, Any],
) -> str:
    raw = json.dumps(
        {
            "entity_type": entity_type,
            "source_database_id": source_database_id,
            "source_ref": source_ref,
            "payload": sanitize_master_data_sync_value(dict(payload or {})),
        },
        ensure_ascii=True,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _build_fallback_canonical_id(*, entity_type: str, source_record_id: str) -> str:
    return f"{normalize_pool_master_data_entity_type(entity_type)}-{str(source_record_id or '').replace('-', '')[:12]}"


def _normalize_text_token(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _normalize_decimal_token(value: Any) -> str:
    if value in (None, ""):
        return ""
    return format(Decimal(str(value)), "f")


def _normalize_date_token(value: Any) -> str:
    if value in (None, ""):
        return ""
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value).strip()


def _digits_only(value: Any) -> str:
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _normalize_conflicting_fields(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({str(item or "").strip() for item in value if str(item or "").strip()})
