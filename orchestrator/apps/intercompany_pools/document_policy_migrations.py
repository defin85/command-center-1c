from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from django.db import transaction

from apps.intercompany_pools.document_policy_contract import (
    DOCUMENT_POLICY_METADATA_KEY,
    resolve_document_policy_from_edge_metadata,
)
from apps.intercompany_pools.metadata_catalog import (
    MetadataCatalogError,
    build_metadata_catalog_api_payload,
    describe_metadata_catalog_snapshot_resolution,
    read_metadata_catalog_snapshot,
    validate_document_policy_references,
)
from apps.intercompany_pools.models import OrganizationPool, PoolEdgeVersion
from apps.intercompany_pools.workflow_bindings_store import (
    PoolWorkflowBindingRevisionConflictError,
    PoolWorkflowBindingStoreError,
    list_canonical_pool_workflow_bindings,
    upsert_canonical_pool_workflow_binding,
)
from apps.templates.workflow.decision_tables import (
    build_decision_table_ref,
    build_decision_table_metadata_context,
    build_decision_table_source_provenance,
    create_decision_table_revision,
)
from apps.templates.workflow.models import DecisionTable


class DocumentPolicyMigrationError(ValueError):
    def __init__(self, *, code: str, detail: str, status_code: int = 400) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class DocumentPolicyMigrationResult:
    decision: DecisionTable
    metadata_context: dict[str, Any]
    migration_report: dict[str, Any]
    created: bool


def migrate_legacy_edge_document_policy(
    *,
    tenant_id: str,
    pool: OrganizationPool,
    edge_version: PoolEdgeVersion,
    created_by=None,
    actor_username: str = "",
    decision_table_id: str = "",
    name: str = "",
    description: str = "",
) -> DocumentPolicyMigrationResult:
    if edge_version.pool_id != pool.id:
        raise DocumentPolicyMigrationError(
            code="POOL_EDGE_NOT_FOUND",
            detail="Pool edge does not belong to the requested pool.",
            status_code=404,
        )

    policy = resolve_document_policy_from_edge_metadata(metadata=edge_version.metadata)
    if policy is None:
        raise DocumentPolicyMigrationError(
            code="POOL_DOCUMENT_POLICY_NOT_FOUND",
            detail="edge.metadata.document_policy is missing for the requested edge.",
        )

    child_database = getattr(edge_version.child_node.organization, "database", None)
    if child_database is None:
        raise DocumentPolicyMigrationError(
            code="POOL_METADATA_CONTEXT_REQUIRED",
            detail="Child organization must be linked to database for document policy migration.",
        )

    try:
        snapshot, source = read_metadata_catalog_snapshot(
            tenant_id=tenant_id,
            database=child_database,
            requested_by_username=str(actor_username or "").strip(),
            allow_cold_bootstrap=True,
        )
    except MetadataCatalogError as exc:
        raise DocumentPolicyMigrationError(
            code=exc.code,
            detail=exc.detail,
            status_code=exc.status_code,
        ) from exc
    referential_errors = validate_document_policy_references(policy=policy, snapshot=snapshot)
    if referential_errors:
        first_error = referential_errors[0]
        raise DocumentPolicyMigrationError(
            code=str(first_error.get("code") or "POOL_METADATA_REFERENCE_INVALID"),
            detail=str(
                first_error.get("detail") or "Legacy document policy references are invalid."
            ),
        )

    resolution = describe_metadata_catalog_snapshot_resolution(
        tenant_id=tenant_id,
        database=child_database,
        snapshot=snapshot,
    )
    metadata_context = build_metadata_catalog_api_payload(
        database=child_database,
        snapshot=snapshot,
        source=source,
        resolution=resolution,
    )
    stored_metadata_context = (
        build_decision_table_metadata_context(metadata_context=metadata_context) or {}
    )
    source_provenance = _build_source_provenance(pool=pool, edge_version=edge_version, policy=policy)
    stored_source_provenance = (
        build_decision_table_source_provenance(source_provenance=source_provenance) or {}
    )

    normalized_decision_table_id = str(decision_table_id or "").strip() or _build_decision_table_id(
        pool=pool,
        edge_version=edge_version,
    )
    latest = (
        DecisionTable.objects.filter(decision_table_id=normalized_decision_table_id)
        .order_by("-version_number", "-created_at")
        .first()
    )
    if latest is not None and latest.decision_key != DOCUMENT_POLICY_METADATA_KEY:
        raise DocumentPolicyMigrationError(
            code="DECISION_TABLE_KEY_CONFLICT",
            detail=(
                f"Decision table '{normalized_decision_table_id}' already exists with "
                f"decision_key '{latest.decision_key}'."
            ),
        )

    with transaction.atomic():
        if latest is not None and _can_reuse_existing_revision(
            decision_table=latest,
            policy=policy,
            metadata_context=stored_metadata_context,
            source_provenance=stored_source_provenance,
        ):
            decision = latest
            created = False
            reused_existing_revision = True
        else:
            decision = create_decision_table_revision(
                contract={
                    "decision_table_id": normalized_decision_table_id,
                    "decision_key": DOCUMENT_POLICY_METADATA_KEY,
                    "name": str(name or "").strip()
                    or _build_decision_name(pool=pool, edge_version=edge_version),
                    "description": str(description or "").strip()
                    or (
                        "Migrated from edge.metadata.document_policy "
                        f"for pool '{pool.code}' edge {edge_version.id}."
                    ),
                    "inputs": [],
                    "outputs": [
                        {
                            "name": DOCUMENT_POLICY_METADATA_KEY,
                            "value_type": "json",
                            "required": True,
                        }
                    ],
                    "rules": [
                        {
                            "rule_id": "legacy-edge-default",
                            "priority": 0,
                            "conditions": {},
                            "outputs": {DOCUMENT_POLICY_METADATA_KEY: policy},
                        }
                    ],
                    "hit_policy": "first_match",
                    "validation_mode": "fail_closed",
                    "metadata_context": stored_metadata_context,
                    "source_provenance": stored_source_provenance,
                    "parent_version_id": str(latest.id) if latest is not None else None,
                },
                created_by=created_by,
                parent_version=latest,
            )
            created = True
            reused_existing_revision = False
        affected_bindings_count = _update_affected_pool_workflow_bindings(
            pool=pool,
            decision=decision,
            actor_username=actor_username,
        )

    return DocumentPolicyMigrationResult(
        decision=decision,
        metadata_context=metadata_context,
        migration_report=_build_migration_report(
            pool=pool,
            edge_version=edge_version,
            decision=decision,
            source_provenance=stored_source_provenance,
            created=created,
            reused_existing_revision=reused_existing_revision,
            binding_update_required=affected_bindings_count == 0,
        ),
        created=created,
    )


def _build_decision_table_id(*, pool: OrganizationPool, edge_version: PoolEdgeVersion) -> str:
    raw_identity = (
        f"{pool.id}:{edge_version.parent_node.organization_id}:"
        f"{edge_version.child_node.organization_id}:{DOCUMENT_POLICY_METADATA_KEY}"
    )
    return f"legacy-doc-policy-{hashlib.sha256(raw_identity.encode('utf-8')).hexdigest()[:16]}"


def _build_decision_name(*, pool: OrganizationPool, edge_version: PoolEdgeVersion) -> str:
    parent_name = str(edge_version.parent_node.organization.name or "").strip() or str(
        edge_version.parent_node.organization_id
    )
    child_name = str(edge_version.child_node.organization.name or "").strip() or str(
        edge_version.child_node.organization_id
    )
    return f"{pool.code}: {parent_name} -> {child_name} document policy"


def _build_source_provenance(
    *,
    pool: OrganizationPool,
    edge_version: PoolEdgeVersion,
    policy: Mapping[str, Any],
) -> dict[str, str]:
    child_database = getattr(edge_version.child_node.organization, "database", None)
    return {
        "kind": "legacy_edge_document_policy",
        "source_path": "edge.metadata.document_policy",
        "pool_id": str(pool.id),
        "edge_version_id": str(edge_version.id),
        "parent_node_version_id": str(edge_version.parent_node_id),
        "child_node_version_id": str(edge_version.child_node_id),
        "parent_organization_id": str(edge_version.parent_node.organization_id),
        "child_organization_id": str(edge_version.child_node.organization_id),
        "child_database_id": str(getattr(child_database, "id", "") or ""),
        "effective_from": edge_version.effective_from.isoformat(),
        "effective_to": edge_version.effective_to.isoformat() if edge_version.effective_to else "",
        "legacy_policy_hash": hashlib.sha256(
            json.dumps(dict(policy), sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
    }


def _can_reuse_existing_revision(
    *,
    decision_table: DecisionTable,
    policy: Mapping[str, Any],
    metadata_context: Mapping[str, Any],
    source_provenance: Mapping[str, Any],
) -> bool:
    existing_policy = _extract_document_policy(decision_table=decision_table)
    if existing_policy != dict(policy):
        return False
    stored_metadata_context = build_decision_table_metadata_context(
        metadata_context=decision_table.metadata_context
        if isinstance(decision_table.metadata_context, Mapping)
        else None
    )
    if stored_metadata_context != dict(metadata_context):
        return False
    stored_source_provenance = build_decision_table_source_provenance(
        source_provenance=decision_table.source_provenance
        if isinstance(decision_table.source_provenance, Mapping)
        else None
    )
    return stored_source_provenance == dict(source_provenance)


def _extract_document_policy(*, decision_table: DecisionTable) -> dict[str, Any] | None:
    rules = list(decision_table.rules or [])
    if not rules:
        return None
    outputs = rules[0].get("outputs") if isinstance(rules[0], Mapping) else None
    if not isinstance(outputs, Mapping):
        return None
    policy = outputs.get(DOCUMENT_POLICY_METADATA_KEY)
    if not isinstance(policy, Mapping):
        return None
    return dict(policy)


def _update_affected_pool_workflow_bindings(
    *,
    pool: OrganizationPool,
    decision: DecisionTable,
    actor_username: str,
) -> int:
    canonical_bindings = list_canonical_pool_workflow_bindings(pool=pool)
    migrated_decision_ref = build_decision_table_ref(decision_table=decision).model_dump(mode="json")

    for binding in canonical_bindings:
        rewritten_decisions = _rewrite_document_policy_binding_decisions(
            decisions=binding.get("decisions"),
            migrated_decision_ref=migrated_decision_ref,
        )
        if rewritten_decisions == list(binding.get("decisions") or []):
            continue
        updated_payload = dict(binding)
        updated_payload["decisions"] = rewritten_decisions
        try:
            upsert_canonical_pool_workflow_binding(
                pool=pool,
                workflow_binding=updated_payload,
                actor_username=actor_username,
            )
        except PoolWorkflowBindingStoreError as exc:
            status_code = 409 if isinstance(exc, PoolWorkflowBindingRevisionConflictError) else 400
            raise DocumentPolicyMigrationError(
                code="POOL_WORKFLOW_BINDING_UPDATE_FAILED",
                detail=(
                    "Failed to update canonical workflow binding "
                    f"'{binding.get('binding_id')}' with migrated document policy ref."
                ),
                status_code=status_code,
            ) from exc
    return len(canonical_bindings)


def _rewrite_document_policy_binding_decisions(
    *,
    decisions: object,
    migrated_decision_ref: Mapping[str, Any],
) -> list[dict[str, Any]]:
    existing_decisions = [
        dict(decision_ref)
        for decision_ref in decisions
        if isinstance(decision_ref, Mapping)
    ] if isinstance(decisions, list) else []
    rewritten_decisions: list[dict[str, Any]] = []
    document_policy_pinned = False

    for decision_ref in existing_decisions:
        if str(decision_ref.get("decision_key") or "").strip() == DOCUMENT_POLICY_METADATA_KEY:
            if not document_policy_pinned:
                rewritten_decisions.append(dict(migrated_decision_ref))
                document_policy_pinned = True
            continue
        rewritten_decisions.append(decision_ref)

    if not document_policy_pinned:
        rewritten_decisions.append(dict(migrated_decision_ref))
    return rewritten_decisions


def _build_migration_report(
    *,
    pool: OrganizationPool,
    edge_version: PoolEdgeVersion,
    decision: DecisionTable,
    source_provenance: Mapping[str, Any],
    created: bool,
    reused_existing_revision: bool,
    binding_update_required: bool,
) -> dict[str, Any]:
    source = dict(source_provenance)
    source["pool_code"] = pool.code
    source["parent_organization_name"] = edge_version.parent_node.organization.name
    source["child_organization_name"] = edge_version.child_node.organization.name
    return {
        "created": created,
        "reused_existing_revision": reused_existing_revision,
        "binding_update_required": binding_update_required,
        "source": source,
        "decision_ref": {
            "decision_id": str(decision.id),
            "decision_table_id": decision.decision_table_id,
            "decision_revision": decision.version_number,
        },
    }


__all__ = [
    "DocumentPolicyMigrationError",
    "DocumentPolicyMigrationResult",
    "migrate_legacy_edge_document_policy",
]
