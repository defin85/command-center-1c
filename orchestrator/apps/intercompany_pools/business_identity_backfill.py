from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from django.db import transaction

from apps.databases.models import Database
from apps.intercompany_pools.business_configuration_profile import get_business_configuration_profile
from apps.intercompany_pools.document_policy_contract import DOCUMENT_POLICY_METADATA_KEY
from apps.intercompany_pools.metadata_catalog import (
    build_metadata_catalog_api_payload,
    describe_metadata_catalog_snapshot_resolution,
)
from apps.intercompany_pools.models import (
    PoolEdgeVersion,
    PoolODataMetadataCatalogScopeResolution,
    PoolODataMetadataCatalogSnapshot,
)
from apps.templates.workflow.decision_tables import (
    build_decision_table_metadata_context,
    build_decision_table_source_provenance,
)
from apps.templates.workflow.models import DecisionTable


_RESOLUTION_ORDER = ("-confirmed_at", "-updated_at", "-created_at")
_SNAPSHOT_ORDER = ("-fetched_at", "-created_at")


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _resolve_extensions_fingerprint(*, database: Database) -> str:
    extensions_fingerprint = ""
    snapshot = getattr(database, "extensions_snapshot", None)
    if snapshot is not None and isinstance(getattr(snapshot, "snapshot", None), dict):
        extensions_fingerprint = hashlib.sha256(_canonical_json_bytes(snapshot.snapshot)).hexdigest()
    return extensions_fingerprint


def _build_business_scope(*, database: Database, profile: Mapping[str, Any]) -> dict[str, str]:
    return {
        "config_name": str(profile.get("config_name") or "").strip(),
        "config_version": str(profile.get("config_version") or "").strip(),
    }


def _matching_scope_resolution(*, database: Database, scope: Mapping[str, str]):
    return (
        PoolODataMetadataCatalogScopeResolution.objects.select_related("snapshot")
        .filter(
            database=database,
            config_name=scope["config_name"],
            config_version=scope["config_version"],
        )
        .order_by(*_RESOLUTION_ORDER)
        .first()
    )


def _latest_database_scope_resolution(*, database: Database):
    return (
        PoolODataMetadataCatalogScopeResolution.objects.select_related("snapshot")
        .filter(database=database)
        .order_by(*_RESOLUTION_ORDER)
        .first()
    )


def _latest_database_current_snapshot(*, database: Database):
    return (
        PoolODataMetadataCatalogSnapshot.objects.filter(database=database, is_current=True)
        .order_by(*_SNAPSHOT_ORDER)
        .first()
    )


def _shared_scope_snapshot(*, tenant_id: str, scope: Mapping[str, str]):
    return (
        PoolODataMetadataCatalogSnapshot.objects.filter(
            tenant_id=tenant_id,
            config_name=scope["config_name"],
            config_version=scope["config_version"],
            is_current=True,
        )
        .order_by(*_SNAPSHOT_ORDER)
        .first()
    )


def _select_seed_snapshot(*, database: Database, scope: Mapping[str, str]):
    matching_resolution = _matching_scope_resolution(database=database, scope=scope)
    if matching_resolution is not None and matching_resolution.snapshot_id:
        return matching_resolution.snapshot

    shared_snapshot = _shared_scope_snapshot(tenant_id=str(database.tenant_id), scope=scope)
    if shared_snapshot is not None:
        return shared_snapshot

    resolution = _latest_database_scope_resolution(database=database)
    if resolution is not None and resolution.snapshot_id:
        return resolution.snapshot

    return _latest_database_current_snapshot(database=database)


def _materialize_scope_snapshot(
    *,
    database: Database,
    scope: Mapping[str, str],
    seed_snapshot: PoolODataMetadataCatalogSnapshot,
    extensions_fingerprint: str,
    dry_run: bool,
) -> tuple[PoolODataMetadataCatalogSnapshot, bool]:
    if (
        str(seed_snapshot.config_name or "") == scope["config_name"]
        and str(seed_snapshot.config_version or "") == scope["config_version"]
    ):
        return seed_snapshot, False

    existing = (
        PoolODataMetadataCatalogSnapshot.objects.filter(
            tenant_id=database.tenant_id,
            config_name=scope["config_name"],
            config_version=scope["config_version"],
            catalog_version=seed_snapshot.catalog_version,
        )
        .order_by(*_SNAPSHOT_ORDER)
        .first()
    )
    if existing is not None:
        if not existing.is_current and not dry_run:
            existing.is_current = True
            existing.save(update_fields=["is_current", "updated_at"])
            return existing, True
        return existing, False

    if dry_run:
        return seed_snapshot, True

    created = PoolODataMetadataCatalogSnapshot.objects.create(
        tenant_id=database.tenant_id,
        database=seed_snapshot.database,
        config_name=scope["config_name"],
        config_version=scope["config_version"],
        extensions_fingerprint=extensions_fingerprint,
        metadata_hash=seed_snapshot.metadata_hash,
        catalog_version=seed_snapshot.catalog_version,
        payload=seed_snapshot.payload if isinstance(seed_snapshot.payload, dict) else {},
        source=seed_snapshot.source,
        fetched_at=seed_snapshot.fetched_at,
        is_current=True,
    )
    return created, True


def backfill_database_business_identity_scope(
    *,
    database: Database,
    dry_run: bool = False,
) -> dict[str, Any]:
    profile = get_business_configuration_profile(database=database)
    if profile is None:
        return {"updated": False, "unresolved_reason": "profile_missing"}

    scope = _build_business_scope(database=database, profile=profile)
    extensions_fingerprint = _resolve_extensions_fingerprint(database=database)
    if not scope["config_name"] or not scope["config_version"]:
        return {"updated": False, "unresolved_reason": "profile_incomplete"}

    seed_snapshot = _select_seed_snapshot(database=database, scope=scope)
    if seed_snapshot is None:
        return {"updated": False, "unresolved_reason": "snapshot_missing"}

    snapshot_updated = False
    resolution_updated = False
    with transaction.atomic():
        canonical_snapshot, snapshot_updated = _materialize_scope_snapshot(
            database=database,
            scope=scope,
            seed_snapshot=seed_snapshot,
            extensions_fingerprint=extensions_fingerprint,
            dry_run=dry_run,
        )
        resolution = _matching_scope_resolution(database=database, scope=scope)
        if resolution is None:
            resolution_updated = True
            if not dry_run:
                PoolODataMetadataCatalogScopeResolution.objects.create(
                    tenant_id=database.tenant_id,
                    database=database,
                    snapshot=canonical_snapshot,
                    config_name=scope["config_name"],
                    config_version=scope["config_version"],
                    extensions_fingerprint=extensions_fingerprint,
                    confirmed_at=seed_snapshot.fetched_at,
                )
        elif (
            resolution.snapshot_id != canonical_snapshot.id
            or str(resolution.extensions_fingerprint or "") != extensions_fingerprint
            or resolution.confirmed_at != seed_snapshot.fetched_at
        ):
            resolution_updated = True
            if not dry_run:
                resolution.snapshot = canonical_snapshot
                resolution.extensions_fingerprint = extensions_fingerprint
                resolution.confirmed_at = seed_snapshot.fetched_at
                resolution.save(
                    update_fields=[
                        "snapshot",
                        "extensions_fingerprint",
                        "confirmed_at",
                        "updated_at",
                    ]
                )

    return {
        "updated": bool(snapshot_updated or resolution_updated),
        "snapshot_updated": bool(snapshot_updated),
        "resolution_updated": bool(resolution_updated),
        "snapshot_id": str(canonical_snapshot.id),
        "config_name": scope["config_name"],
        "config_version": scope["config_version"],
    }


def _snapshot_by_id(snapshot_id: str):
    token = str(snapshot_id or "").strip()
    if not token:
        return None
    return (
        PoolODataMetadataCatalogSnapshot.objects.select_related("database")
        .filter(id=token)
        .first()
    )


def _resolve_decision_source_database(
    *,
    stored_context: Mapping[str, Any] | None,
    source_provenance: Mapping[str, Any] | None,
    stored_snapshot: PoolODataMetadataCatalogSnapshot | None,
):
    candidate_ids = [
        str((stored_context or {}).get("database_id") or "").strip(),
        str((stored_context or {}).get("provenance_database_id") or "").strip(),
        str((source_provenance or {}).get("child_database_id") or "").strip(),
        str(getattr(stored_snapshot, "database_id", "") or "").strip(),
    ]
    for candidate_id in candidate_ids:
        if not candidate_id:
            continue
        database = Database.objects.filter(id=candidate_id).first()
        if database is not None:
            return database

    edge_version_id = str((source_provenance or {}).get("edge_version_id") or "").strip()
    if edge_version_id:
        edge = (
            PoolEdgeVersion.objects.select_related("child_node__organization__database")
            .filter(id=edge_version_id)
            .first()
        )
        database = getattr(getattr(getattr(edge, "child_node", None), "organization", None), "database", None)
        if database is not None:
            return database
    return None


def _select_decision_snapshot(
    *,
    database: Database,
    scope: Mapping[str, str],
    stored_snapshot: PoolODataMetadataCatalogSnapshot | None,
):
    matching_resolution = _matching_scope_resolution(database=database, scope=scope)
    if matching_resolution is not None and matching_resolution.snapshot_id:
        return matching_resolution.snapshot

    shared_snapshot = _shared_scope_snapshot(tenant_id=str(database.tenant_id), scope=scope)
    if shared_snapshot is not None:
        return shared_snapshot

    if stored_snapshot is not None:
        return stored_snapshot

    resolution = _latest_database_scope_resolution(database=database)
    if resolution is not None and resolution.snapshot_id:
        return resolution.snapshot

    return _latest_database_current_snapshot(database=database)


def backfill_decision_table_business_metadata_context(
    *,
    decision_table: DecisionTable,
    dry_run: bool = False,
) -> dict[str, Any]:
    stored_context = build_decision_table_metadata_context(
        metadata_context=decision_table.metadata_context
        if isinstance(decision_table.metadata_context, Mapping)
        else None
    )
    if decision_table.decision_key != DOCUMENT_POLICY_METADATA_KEY:
        return {
            "metadata_context": stored_context,
            "updated": False,
            "unresolved_reason": None,
        }

    source_provenance = build_decision_table_source_provenance(
        source_provenance=decision_table.source_provenance
        if isinstance(decision_table.source_provenance, Mapping)
        else None
    )
    stored_snapshot = _snapshot_by_id(str((stored_context or {}).get("snapshot_id") or ""))
    database = _resolve_decision_source_database(
        stored_context=stored_context,
        source_provenance=source_provenance,
        stored_snapshot=stored_snapshot,
    )
    if database is None:
        return {
            "metadata_context": stored_context,
            "updated": False,
            "unresolved_reason": "source_database_missing",
        }

    profile = get_business_configuration_profile(database=database)
    if profile is None:
        return {
            "metadata_context": stored_context,
            "updated": False,
            "unresolved_reason": "profile_missing",
        }

    scope = _build_business_scope(database=database, profile=profile)
    snapshot = _select_decision_snapshot(
        database=database,
        scope=scope,
        stored_snapshot=stored_snapshot,
    )
    if snapshot is None:
        return {
            "metadata_context": stored_context,
            "updated": False,
            "unresolved_reason": "snapshot_missing",
        }

    resolution = describe_metadata_catalog_snapshot_resolution(
        tenant_id=str(snapshot.tenant_id),
        database=database,
        snapshot=snapshot,
    )
    payload = build_metadata_catalog_api_payload(
        database=database,
        snapshot=snapshot,
        source=snapshot.source,
        resolution=resolution,
    )
    resolved_context = build_decision_table_metadata_context(metadata_context=payload)
    if resolved_context is None:
        return {
            "metadata_context": stored_context,
            "updated": False,
            "unresolved_reason": "resolved_context_missing",
        }

    updated = stored_context != resolved_context
    if updated and not dry_run:
        decision_table.metadata_context = resolved_context
        decision_table.save(update_fields=["metadata_context", "updated_at"])

    return {
        "metadata_context": resolved_context,
        "updated": updated,
        "unresolved_reason": None,
    }


def run_business_identity_backfill(
    *,
    dry_run: bool = False,
    tenant_id: str | None = None,
    database_id: str | None = None,
    decision_id: str | None = None,
) -> dict[str, Any]:
    databases = Database.objects.all().order_by("id")
    if tenant_id:
        databases = databases.filter(tenant_id=str(tenant_id))
    if database_id:
        databases = databases.filter(id=str(database_id))

    decisions = DecisionTable.objects.filter(decision_key=DOCUMENT_POLICY_METADATA_KEY).order_by("id")
    if decision_id:
        decisions = decisions.filter(id=str(decision_id))

    result = {
        "dry_run": dry_run,
        "databases_scanned": 0,
        "scope_backfilled": 0,
        "scope_unresolved": [],
        "decisions_scanned": 0,
        "decision_contexts_backfilled": 0,
        "decision_context_unresolved": [],
    }

    for database in databases:
        result["databases_scanned"] += 1
        scope_result = backfill_database_business_identity_scope(database=database, dry_run=dry_run)
        if scope_result.get("updated"):
            result["scope_backfilled"] += 1
        unresolved_reason = str(scope_result.get("unresolved_reason") or "").strip()
        if unresolved_reason:
            result["scope_unresolved"].append(
                {
                    "database_id": str(database.id),
                    "reason": unresolved_reason,
                }
            )

    for decision in decisions:
        result["decisions_scanned"] += 1
        decision_result = backfill_decision_table_business_metadata_context(
            decision_table=decision,
            dry_run=dry_run,
        )
        if decision_result.get("updated"):
            result["decision_contexts_backfilled"] += 1
        unresolved_reason = str(decision_result.get("unresolved_reason") or "").strip()
        if unresolved_reason:
            result["decision_context_unresolved"].append(
                {
                    "decision_id": str(decision.id),
                    "decision_table_id": str(decision.decision_table_id or ""),
                    "reason": unresolved_reason,
                }
            )

    return result


__all__ = [
    "backfill_database_business_identity_scope",
    "backfill_decision_table_business_metadata_context",
    "run_business_identity_backfill",
]
