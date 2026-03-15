from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from hashlib import sha256
from typing import Any, Mapping

from django.utils import timezone

from .document_completeness import (
    ensure_document_mapping_completeness,
    resolve_document_completeness_requirements,
)
from .document_policy_contract import (
    DOCUMENT_POLICY_METADATA_KEY,
    validate_document_policy_v1,
)
from .models import PoolEdgeVersion, PoolNodeVersion, PoolRun


DOCUMENT_PLAN_ARTIFACT_VERSION = "document_plan_artifact.v1"
POOL_RUNTIME_DOCUMENT_PLAN_ARTIFACT_CONTEXT_KEY = "pool_runtime_document_plan_artifact"
POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_CONTEXT_KEY = "pool_runtime_compiled_document_policy"
POOL_RUNTIME_COMPILED_DOCUMENT_POLICY_SLOTS_CONTEXT_KEY = "pool_runtime_compiled_document_policy_slots"
POOL_RUNTIME_DOCUMENT_POLICY_SOURCE_CONTEXT_KEY = "pool_runtime_document_policy_source"
POOL_DOCUMENT_PLAN_ARTIFACT_INVALID = "POOL_DOCUMENT_PLAN_ARTIFACT_INVALID"
POOL_DOCUMENT_POLICY_SLOT_SELECTOR_MISSING = "POOL_DOCUMENT_POLICY_SLOT_SELECTOR_MISSING"
POOL_DOCUMENT_POLICY_SLOT_NOT_BOUND = "POOL_DOCUMENT_POLICY_SLOT_NOT_BOUND"
POOL_DOCUMENT_POLICY_SLOT_DUPLICATE = "POOL_DOCUMENT_POLICY_SLOT_DUPLICATE"
POOL_DOCUMENT_POLICY_SLOT_OUTPUT_INVALID = "POOL_DOCUMENT_POLICY_SLOT_OUTPUT_INVALID"
POOL_DOCUMENT_POLICY_SLOT_COVERAGE_AMBIGUOUS = "POOL_DOCUMENT_POLICY_SLOT_COVERAGE_AMBIGUOUS"
POOL_DOCUMENT_POLICY_LEGACY_SOURCE_REJECTED = "POOL_DOCUMENT_POLICY_LEGACY_SOURCE_REJECTED"

REQUIRED_DOCUMENT_PLAN_ARTIFACT_FIELDS = {
    "version",
    "run_id",
    "distribution_artifact_ref",
    "topology_version_ref",
    "policy_refs",
    "targets",
    "compile_summary",
}
_DERIVED_MAPPING_KEY = "$derive"
_DERIVED_MAPPING_OPERATIONS = {
    "add",
    "sub",
    "mul",
    "div",
}


def compile_document_plan_artifact_v1(
    *,
    run: PoolRun,
    distribution_artifact: Mapping[str, Any],
    topology: Mapping[str, Any],
    compiled_document_policy_slots: Mapping[str, Any] | None = None,
    compiled_document_policy: Mapping[str, Any] | None = None,
    document_policy_source: str | None = None,
) -> dict[str, Any] | None:
    edge_allocations = distribution_artifact.get("edge_allocations")
    if not isinstance(edge_allocations, list):
        return None

    edge_models_raw = topology.get("edge_models")
    node_models_raw = topology.get("node_models")
    if not isinstance(edge_models_raw, Mapping) or not isinstance(node_models_raw, Mapping):
        return None

    pool_metadata = run.pool.metadata if isinstance(run.pool.metadata, Mapping) else {}
    normalized_compiled_policy_slots = validate_compiled_document_policy_slots_snapshot(
        compiled_document_policy_slots
    )
    normalized_compiled_policy = (
        validate_document_policy_v1(policy=compiled_document_policy)
        if isinstance(compiled_document_policy, Mapping)
        else None
    )
    normalized_document_policy_source = str(document_policy_source or "").strip() or None
    targets_by_database: dict[str, dict[str, Any]] = {}
    policy_refs: list[dict[str, Any]] = []
    seen_policy_refs: set[tuple[str, str]] = set()
    compiled_edges = 0
    chains_count = 0
    documents_count = 0

    allocations = sorted(
        (
            dict(item)
            for item in edge_allocations
            if isinstance(item, Mapping)
        ),
        key=lambda item: (
            str(item.get("parent_node_id") or ""),
            str(item.get("child_node_id") or ""),
        ),
    )

    for allocation in allocations:
        parent_node_id = str(allocation.get("parent_node_id") or "").strip()
        child_node_id = str(allocation.get("child_node_id") or "").strip()
        if not parent_node_id or not child_node_id:
            continue

        amount = _parse_decimal(allocation.get("amount"))
        if amount is None or amount <= Decimal("0"):
            continue
        amount_text = _decimal_to_string(amount)

        edge_key = (parent_node_id, child_node_id)
        edge_model = edge_models_raw.get(edge_key)
        child_node = node_models_raw.get(child_node_id)
        if not isinstance(edge_model, PoolEdgeVersion) or not isinstance(child_node, PoolNodeVersion):
            continue

        database_id = (
            str(child_node.organization.database_id)
            if getattr(child_node.organization, "database_id", None)
            else ""
        )
        if not database_id:
            continue

        edge_ref = {
            "parent_node_id": parent_node_id,
            "child_node_id": child_node_id,
        }
        edge_metadata = edge_model.metadata if isinstance(edge_model.metadata, Mapping) else {}
        if normalized_compiled_policy_slots is not None:
            slot_key = _resolve_document_policy_key_for_edge(
                edge_metadata=edge_metadata,
                edge_ref=edge_ref,
            )
            slot_projection = normalized_compiled_policy_slots.get(slot_key)
            if slot_projection is None:
                raise ValueError(
                    f"{POOL_DOCUMENT_POLICY_SLOT_NOT_BOUND}: "
                    f"binding slot '{slot_key}' is not bound for edge "
                    f"{parent_node_id}->{child_node_id}"
                )
            policy = slot_projection["document_policy"]
            source = slot_projection["document_policy_source"]
        elif normalized_compiled_policy is not None:
            policy = normalized_compiled_policy
            source = normalized_document_policy_source or "workflow_binding.decision_table"
        else:
            if _has_legacy_document_policy_payload(
                edge_metadata=edge_metadata,
                pool_metadata=pool_metadata,
            ):
                raise ValueError(
                    f"{POOL_DOCUMENT_POLICY_LEGACY_SOURCE_REJECTED}: legacy topology "
                    f"document_policy is not allowed for edge {parent_node_id}->{child_node_id}"
                )
            policy, source = None, None
        if policy is None:
            continue

        policy_ref_key = (parent_node_id, child_node_id)
        if policy_ref_key not in seen_policy_refs:
            policy_refs.append(
                {
                    "edge_ref": edge_ref,
                    "policy_version": str(policy.get("version") or ""),
                    "source": source,
                }
            )
            seen_policy_refs.add(policy_ref_key)

        chain_payloads = _compile_chains_for_edge(
            run=run,
            policy=policy,
            edge_ref=edge_ref,
            source=source,
            database_id=database_id,
            amount_text=amount_text,
        )
        if not chain_payloads:
            continue

        target = targets_by_database.setdefault(
            database_id,
            {
                "database_id": database_id,
                "chains": [],
            },
        )
        target["chains"].extend(chain_payloads)
        compiled_edges += 1
        chains_count += len(chain_payloads)
        documents_count += sum(
            len(chain.get("documents") or [])
            for chain in chain_payloads
            if isinstance(chain, Mapping)
        )

    if not targets_by_database:
        return None

    targets = [targets_by_database[database_id] for database_id in sorted(targets_by_database)]
    topology_version_ref = str(distribution_artifact.get("topology_version_ref") or "").strip()
    artifact = {
        "version": DOCUMENT_PLAN_ARTIFACT_VERSION,
        "run_id": str(run.id),
        "distribution_artifact_ref": {
            "version": str(distribution_artifact.get("version") or "").strip(),
            "topology_version_ref": topology_version_ref,
        },
        "topology_version_ref": topology_version_ref,
        "policy_refs": policy_refs,
        "targets": targets,
        "compile_summary": {
            "compiled_edges": compiled_edges,
            "targets_count": len(targets),
            "chains_count": chains_count,
            "documents_count": documents_count,
            "compiled_at": timezone.now().isoformat(),
        },
    }
    return validate_document_plan_artifact_v1(artifact=artifact)


def validate_compiled_document_policy_slots_snapshot(
    compiled_document_policy_slots: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]] | None:
    if not isinstance(compiled_document_policy_slots, Mapping):
        return None

    normalized: dict[str, dict[str, Any]] = {}
    for raw_slot_key, raw_slot_projection in dict(compiled_document_policy_slots).items():
        slot_key = str(raw_slot_key or "").strip()
        if not slot_key:
            raise ValueError(
                f"{POOL_DOCUMENT_POLICY_SLOT_OUTPUT_INVALID}: slot key must be a non-empty string"
            )
        if slot_key in normalized:
            raise ValueError(
                f"{POOL_DOCUMENT_POLICY_SLOT_DUPLICATE}: duplicate slot key '{slot_key}'"
            )
        if not isinstance(raw_slot_projection, Mapping):
            raise ValueError(
                f"{POOL_DOCUMENT_POLICY_SLOT_OUTPUT_INVALID}: slot '{slot_key}' must be an object"
            )
        slot_projection = dict(raw_slot_projection)
        raw_document_policy = slot_projection.get("document_policy")
        if not isinstance(raw_document_policy, Mapping):
            raise ValueError(
                f"{POOL_DOCUMENT_POLICY_SLOT_OUTPUT_INVALID}: "
                f"slot '{slot_key}' document_policy must be an object"
            )
        document_policy_source = str(slot_projection.get("document_policy_source") or "").strip()
        if not document_policy_source:
            raise ValueError(
                f"{POOL_DOCUMENT_POLICY_SLOT_OUTPUT_INVALID}: "
                f"slot '{slot_key}' document_policy_source is required"
            )
        normalized[slot_key] = {
            **slot_projection,
            "document_policy": validate_document_policy_v1(policy=raw_document_policy),
            "document_policy_source": document_policy_source,
        }
    return normalized


def _resolve_document_policy_key_for_edge(
    *,
    edge_metadata: Mapping[str, Any],
    edge_ref: Mapping[str, str],
) -> str:
    slot_key = str(edge_metadata.get("document_policy_key") or "").strip()
    if slot_key:
        return slot_key
    raise ValueError(
        f"{POOL_DOCUMENT_POLICY_SLOT_SELECTOR_MISSING}: edge "
        f"{str(edge_ref.get('parent_node_id') or '').strip()}->"
        f"{str(edge_ref.get('child_node_id') or '').strip()} requires metadata.document_policy_key"
    )


def _has_legacy_document_policy_payload(
    *,
    edge_metadata: Mapping[str, Any],
    pool_metadata: Mapping[str, Any],
) -> bool:
    return DOCUMENT_POLICY_METADATA_KEY in edge_metadata or DOCUMENT_POLICY_METADATA_KEY in pool_metadata


def validate_document_plan_artifact_v1(*, artifact: Any) -> dict[str, Any]:
    payload = _require_object(
        artifact,
        field_name="document_plan_artifact",
    )
    missing_fields = sorted(
        field_name
        for field_name in REQUIRED_DOCUMENT_PLAN_ARTIFACT_FIELDS
        if field_name not in payload
    )
    if missing_fields:
        raise ValueError(
            f"{POOL_DOCUMENT_PLAN_ARTIFACT_INVALID}: "
            f"missing required artifact fields: {', '.join(missing_fields)}"
        )

    version = _require_string(
        payload.get("version"),
        field_name="document_plan_artifact.version",
    )
    if version != DOCUMENT_PLAN_ARTIFACT_VERSION:
        raise ValueError(
            f"{POOL_DOCUMENT_PLAN_ARTIFACT_INVALID}: unexpected artifact version '{version or '<empty>'}'"
        )

    _require_string(
        payload.get("run_id"),
        field_name="document_plan_artifact.run_id",
    )
    _require_string(
        payload.get("topology_version_ref"),
        field_name="document_plan_artifact.topology_version_ref",
    )

    distribution_ref = _require_object(
        payload.get("distribution_artifact_ref"),
        field_name="document_plan_artifact.distribution_artifact_ref",
    )
    _require_string(
        distribution_ref.get("version"),
        field_name="document_plan_artifact.distribution_artifact_ref.version",
    )
    _require_string(
        distribution_ref.get("topology_version_ref"),
        field_name="document_plan_artifact.distribution_artifact_ref.topology_version_ref",
    )

    policy_refs = _require_array(
        payload.get("policy_refs"),
        field_name="document_plan_artifact.policy_refs",
        require_non_empty=True,
    )
    for index, policy_ref_raw in enumerate(policy_refs):
        policy_ref = _require_object(
            policy_ref_raw,
            field_name=f"document_plan_artifact.policy_refs[{index}]",
        )
        edge_ref = _require_object(
            policy_ref.get("edge_ref"),
            field_name=f"document_plan_artifact.policy_refs[{index}].edge_ref",
        )
        _require_string(
            edge_ref.get("parent_node_id"),
            field_name=f"document_plan_artifact.policy_refs[{index}].edge_ref.parent_node_id",
        )
        _require_string(
            edge_ref.get("child_node_id"),
            field_name=f"document_plan_artifact.policy_refs[{index}].edge_ref.child_node_id",
        )
        _require_string(
            policy_ref.get("policy_version"),
            field_name=f"document_plan_artifact.policy_refs[{index}].policy_version",
        )
        _require_string(
            policy_ref.get("source"),
            field_name=f"document_plan_artifact.policy_refs[{index}].source",
        )

    targets = _require_array(
        payload.get("targets"),
        field_name="document_plan_artifact.targets",
        require_non_empty=True,
    )
    for target_index, target_raw in enumerate(targets):
        target = _require_object(
            target_raw,
            field_name=f"document_plan_artifact.targets[{target_index}]",
        )
        _require_string(
            target.get("database_id"),
            field_name=f"document_plan_artifact.targets[{target_index}].database_id",
        )
        chains = _require_array(
            target.get("chains"),
            field_name=f"document_plan_artifact.targets[{target_index}].chains",
            require_non_empty=True,
        )
        for chain_index, chain_raw in enumerate(chains):
            chain = _require_object(
                chain_raw,
                field_name=(
                    f"document_plan_artifact.targets[{target_index}].chains[{chain_index}]"
                ),
            )
            _require_string(
                chain.get("chain_id"),
                field_name=(
                    f"document_plan_artifact.targets[{target_index}].chains[{chain_index}].chain_id"
                ),
            )
            edge_ref = _require_object(
                chain.get("edge_ref"),
                field_name=(
                    f"document_plan_artifact.targets[{target_index}].chains[{chain_index}].edge_ref"
                ),
            )
            _require_string(
                edge_ref.get("parent_node_id"),
                field_name=(
                    f"document_plan_artifact.targets[{target_index}].chains[{chain_index}].edge_ref.parent_node_id"
                ),
            )
            _require_string(
                edge_ref.get("child_node_id"),
                field_name=(
                    f"document_plan_artifact.targets[{target_index}].chains[{chain_index}].edge_ref.child_node_id"
                ),
            )
            documents = _require_array(
                chain.get("documents"),
                field_name=(
                    f"document_plan_artifact.targets[{target_index}].chains[{chain_index}].documents"
                ),
                require_non_empty=True,
            )
            for document_index, document_raw in enumerate(documents):
                document = _require_object(
                    document_raw,
                    field_name=(
                        "document_plan_artifact.targets"
                        f"[{target_index}].chains[{chain_index}].documents[{document_index}]"
                    ),
                )
                for field_name in (
                    "document_id",
                    "entity_name",
                    "document_role",
                    "invoice_mode",
                    "idempotency_key",
                ):
                    _require_string(
                        document.get(field_name),
                        field_name=(
                            "document_plan_artifact.targets"
                            f"[{target_index}].chains[{chain_index}].documents[{document_index}].{field_name}"
                        ),
                    )
                _require_object(
                    document.get("field_mapping"),
                    field_name=(
                        "document_plan_artifact.targets"
                        f"[{target_index}].chains[{chain_index}].documents[{document_index}].field_mapping"
                    ),
                )
                _require_object(
                    document.get("table_parts_mapping"),
                    field_name=(
                        "document_plan_artifact.targets"
                        f"[{target_index}].chains[{chain_index}].documents[{document_index}].table_parts_mapping"
                    ),
                )
                _require_object(
                    document.get("link_rules"),
                    field_name=(
                        "document_plan_artifact.targets"
                        f"[{target_index}].chains[{chain_index}].documents[{document_index}].link_rules"
                    ),
                )

    compile_summary = _require_object(
        payload.get("compile_summary"),
        field_name="document_plan_artifact.compile_summary",
    )
    for field_name in (
        "compiled_edges",
        "targets_count",
        "chains_count",
        "documents_count",
    ):
        _require_non_negative_int(
            compile_summary.get(field_name),
            field_name=f"document_plan_artifact.compile_summary.{field_name}",
        )
    _require_string(
        compile_summary.get("compiled_at"),
        field_name="document_plan_artifact.compile_summary.compiled_at",
    )
    return payload


def build_publication_payload_from_document_plan_artifact(
    *,
    artifact: Mapping[str, Any],
    run_input: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = run_input if isinstance(run_input, Mapping) else {}
    validated_artifact = validate_document_plan_artifact_v1(artifact=artifact)
    targets = validated_artifact.get("targets")
    target_items = targets if isinstance(targets, list) else []

    documents_by_database: dict[str, list[dict[str, Any]]] = {}
    document_chains_by_database: dict[str, list[dict[str, Any]]] = {}
    resolved_entity_name = ""

    for target_raw in target_items:
        if not isinstance(target_raw, Mapping):
            continue
        database_id = str(target_raw.get("database_id") or "").strip()
        if not database_id:
            continue
        chains_raw = target_raw.get("chains")
        if not isinstance(chains_raw, list):
            continue

        for chain_raw in chains_raw:
            if not isinstance(chain_raw, Mapping):
                continue
            allocation_raw = chain_raw.get("allocation")
            allocation = allocation_raw if isinstance(allocation_raw, Mapping) else {}
            amount = str(allocation.get("amount") or "").strip()
            if not amount:
                continue

            documents_by_database.setdefault(database_id, []).append({"Amount": amount})

            documents_raw = chain_raw.get("documents")
            if not isinstance(documents_raw, list):
                continue
            compiled_documents: list[dict[str, Any]] = []
            for document_raw in documents_raw:
                if not isinstance(document_raw, Mapping):
                    continue
                document = dict(document_raw)
                entity_name = str(document.get("entity_name") or "").strip()
                if not resolved_entity_name and entity_name:
                    resolved_entity_name = entity_name
                field_mapping = _as_object(document.get("field_mapping"))
                table_parts_mapping = _as_object(document.get("table_parts_mapping"))
                link_rules = _as_object(document.get("link_rules"))
                resolved_link_refs = _as_object(document.get("resolved_link_refs"))
                document_payload = _build_document_payload_from_mapping(
                    amount=amount,
                    allocation=allocation,
                    field_mapping=field_mapping,
                    table_parts_mapping=table_parts_mapping,
                    resolved_link_refs=resolved_link_refs,
                )
                compiled_document: dict[str, Any] = {
                    "document_id": str(document.get("document_id") or "").strip(),
                    "entity_name": entity_name,
                    "document_role": str(document.get("document_role") or "").strip(),
                    "idempotency_key": str(document.get("idempotency_key") or "").strip(),
                    "invoice_mode": str(document.get("invoice_mode") or "").strip(),
                    "field_mapping": field_mapping,
                    "table_parts_mapping": table_parts_mapping,
                    "link_rules": link_rules,
                    "payload": document_payload,
                }
                link_to = str(document.get("link_to") or "").strip()
                if link_to:
                    compiled_document["link_to"] = link_to
                if resolved_link_refs:
                    compiled_document["resolved_link_refs"] = resolved_link_refs
                completeness_requirements = document.get("completeness_requirements")
                if isinstance(completeness_requirements, Mapping):
                    compiled_document["completeness_requirements"] = dict(completeness_requirements)
                compiled_documents.append(compiled_document)

            if not compiled_documents:
                continue
            chain_payload = {
                "chain_id": str(chain_raw.get("chain_id") or "").strip(),
                "edge_ref": dict(chain_raw.get("edge_ref") or {}),
                "policy_source": str(chain_raw.get("policy_source") or "").strip(),
                "policy_version": str(chain_raw.get("policy_version") or "").strip(),
                "allocation": {
                    "amount": amount,
                },
                "documents": compiled_documents,
            }
            document_chains_by_database.setdefault(database_id, []).append(chain_payload)

    if not resolved_entity_name:
        resolved_entity_name = str(payload.get("entity_name") or "").strip()

    publication_payload = {
        "entity_name": resolved_entity_name,
        "documents_by_database": documents_by_database,
        "document_chains_by_database": document_chains_by_database,
        "document_plan_artifact": validated_artifact,
        "max_attempts": payload.get("max_attempts"),
        "retry_interval_seconds": payload.get("retry_interval_seconds"),
        "external_key_field": str(payload.get("external_key_field") or "").strip(),
    }
    return {"pool_runtime": publication_payload}


def _compile_chains_for_edge(
    *,
    run: PoolRun,
    policy: Mapping[str, Any],
    edge_ref: Mapping[str, str],
    source: str,
    database_id: str,
    amount_text: str,
) -> list[dict[str, Any]]:
    chains_raw = policy.get("chains")
    if not isinstance(chains_raw, list):
        return []

    compiled_chains: list[dict[str, Any]] = []
    for chain_index, chain in enumerate(chains_raw):
        if not isinstance(chain, Mapping):
            continue
        chain_id = str(chain.get("chain_id") or "").strip()
        if not chain_id:
            continue
        documents_raw = chain.get("documents")
        if not isinstance(documents_raw, list):
            continue

        compiled_documents: list[dict[str, Any]] = []
        for document_index, document in enumerate(documents_raw):
            if not isinstance(document, Mapping):
                continue
            document_id = str(document.get("document_id") or "").strip()
            if not document_id:
                continue
            compiled_document = {
                "document_id": document_id,
                "entity_name": str(document.get("entity_name") or "").strip(),
                "document_role": str(document.get("document_role") or "").strip(),
                "field_mapping": _as_object(document.get("field_mapping")),
                "table_parts_mapping": _as_object(document.get("table_parts_mapping")),
                "link_rules": _as_object(document.get("link_rules")),
                "invoice_mode": str(document.get("invoice_mode") or "").strip(),
                "idempotency_key": _build_document_idempotency_key(
                    run_id=str(run.id),
                    database_id=database_id,
                    edge_ref=edge_ref,
                    chain_id=chain_id,
                    document_id=document_id,
                    amount_text=amount_text,
                ),
            }
            link_to = str(document.get("link_to") or "").strip()
            if link_to:
                compiled_document["link_to"] = link_to
            completeness_requirements = resolve_document_completeness_requirements(
                policy=policy,
                entity_name=compiled_document["entity_name"],
                document=compiled_document,
            )
            normalized_requirements = ensure_document_mapping_completeness(
                document=compiled_document,
                completeness_requirements=completeness_requirements,
                path_prefix=f"document_policy.chains[{chain_index}].documents[{document_index}]",
                error_code="POOL_DOCUMENT_POLICY_MAPPING_INVALID",
            )
            if normalized_requirements is not None:
                compiled_document["completeness_requirements"] = normalized_requirements
            compiled_documents.append(compiled_document)

        if not compiled_documents:
            continue

        compiled_chains.append(
            {
                "chain_id": chain_id,
                "edge_ref": dict(edge_ref),
                "policy_source": source,
                "policy_version": str(policy.get("version") or "").strip(),
                "allocation": {
                    "amount": amount_text,
                },
                "documents": compiled_documents,
            }
        )
    return compiled_chains


def _build_document_idempotency_key(
    *,
    run_id: str,
    database_id: str,
    edge_ref: Mapping[str, str],
    chain_id: str,
    document_id: str,
    amount_text: str,
) -> str:
    payload = {
        "amount": amount_text,
        "chain_id": chain_id,
        "child_node_id": str(edge_ref.get("child_node_id") or "").strip(),
        "database_id": database_id,
        "document_id": document_id,
        "parent_node_id": str(edge_ref.get("parent_node_id") or "").strip(),
        "run_id": run_id,
    }
    digest = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"doc-plan:{digest[:32]}"


def _require_object(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(
            f"{POOL_DOCUMENT_PLAN_ARTIFACT_INVALID}: {field_name} must be an object"
        )
    return dict(value)


def _require_array(
    value: Any,
    *,
    field_name: str,
    require_non_empty: bool = False,
) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(
            f"{POOL_DOCUMENT_PLAN_ARTIFACT_INVALID}: {field_name} must be an array"
        )
    if require_non_empty and not value:
        raise ValueError(
            f"{POOL_DOCUMENT_PLAN_ARTIFACT_INVALID}: {field_name} must be a non-empty array"
        )
    return value


def _require_string(value: Any, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(
            f"{POOL_DOCUMENT_PLAN_ARTIFACT_INVALID}: {field_name} must be a non-empty string"
        )
    return text


def _require_non_negative_int(value: Any, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(
            f"{POOL_DOCUMENT_PLAN_ARTIFACT_INVALID}: {field_name} must be a non-negative integer"
        )
    return value


def _as_object(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _build_document_payload_from_mapping(
    *,
    amount: str,
    allocation: Mapping[str, Any],
    field_mapping: Mapping[str, Any],
    table_parts_mapping: Mapping[str, Any],
    resolved_link_refs: Mapping[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    allocation_payload = dict(allocation)

    for raw_field_name, raw_mapping in field_mapping.items():
        field_name = str(raw_field_name or "").strip()
        if not field_name:
            continue
        resolved_value, is_resolved = _resolve_mapping_value(
            raw_mapping,
            allocation=allocation_payload,
            resolved_link_refs=resolved_link_refs,
        )
        if is_resolved:
            payload[field_name] = resolved_value

    for raw_table_name, raw_rows in table_parts_mapping.items():
        table_name = str(raw_table_name or "").strip()
        if not table_name or not isinstance(raw_rows, list):
            continue
        compiled_rows: list[dict[str, Any]] = []
        for raw_row in raw_rows:
            if not isinstance(raw_row, Mapping):
                continue
            compiled_row: dict[str, Any] = {}
            for raw_column_name, raw_mapping in raw_row.items():
                column_name = str(raw_column_name or "").strip()
                if not column_name:
                    continue
                resolved_value, is_resolved = _resolve_mapping_value(
                    raw_mapping,
                    allocation=allocation_payload,
                    resolved_link_refs=resolved_link_refs,
                )
                if is_resolved:
                    compiled_row[column_name] = resolved_value
            if compiled_row:
                compiled_rows.append(compiled_row)
        if compiled_rows:
            payload[table_name] = compiled_rows

    return payload


def _resolve_mapping_value(
    value: Any,
    *,
    allocation: Mapping[str, Any],
    resolved_link_refs: Mapping[str, Any],
) -> tuple[Any, bool]:
    if isinstance(value, Mapping):
        if _DERIVED_MAPPING_KEY in value:
            return _resolve_derived_mapping_value(
                value,
                allocation=allocation,
                resolved_link_refs=resolved_link_refs,
            )
        payload: dict[str, Any] = {}
        for raw_key, raw_item in value.items():
            key = str(raw_key or "").strip()
            if not key:
                continue
            resolved_value, is_resolved = _resolve_mapping_value(
                raw_item,
                allocation=allocation,
                resolved_link_refs=resolved_link_refs,
            )
            if is_resolved:
                payload[key] = resolved_value
        return payload, bool(payload)

    if isinstance(value, str):
        if value == "":
            return "", True
        token = value.strip()
        if not token:
            return None, False
        if token.startswith("allocation."):
            lookup_path = token.removeprefix("allocation.").strip()
            if not lookup_path:
                return None, False
            return _resolve_dotted_path(allocation, lookup_path)
        if token.endswith(".ref"):
            document_id = token.removesuffix(".ref").strip()
            if not document_id:
                return None, False
            ref_value = str(resolved_link_refs.get(document_id) or "").strip()
            if not ref_value:
                return None, False
            return ref_value, True
        return token, True

    if isinstance(value, list):
        items: list[Any] = []
        for raw_item in value:
            resolved_value, is_resolved = _resolve_mapping_value(
                raw_item,
                allocation=allocation,
                resolved_link_refs=resolved_link_refs,
            )
            if is_resolved:
                items.append(resolved_value)
        return items, bool(items)

    if value is None:
        return None, False
    return value, True


def _resolve_derived_mapping_value(
    value: Mapping[str, Any],
    *,
    allocation: Mapping[str, Any],
    resolved_link_refs: Mapping[str, Any],
) -> tuple[Any, bool]:
    if set(value.keys()) != {_DERIVED_MAPPING_KEY}:
        raise ValueError(
            "POOL_DOCUMENT_POLICY_MAPPING_INVALID: derived expression must not include sibling keys"
        )
    expression = value.get(_DERIVED_MAPPING_KEY)
    if not isinstance(expression, Mapping):
        raise ValueError("POOL_DOCUMENT_POLICY_MAPPING_INVALID: $derive must be an object")

    op = str(expression.get("op") or "").strip().lower()
    if op not in _DERIVED_MAPPING_OPERATIONS:
        raise ValueError(
            "POOL_DOCUMENT_POLICY_MAPPING_INVALID: derived expression op must be one of "
            f"{', '.join(sorted(_DERIVED_MAPPING_OPERATIONS))}"
        )
    args = expression.get("args")
    if not isinstance(args, list):
        raise ValueError("POOL_DOCUMENT_POLICY_MAPPING_INVALID: derived expression args must be an array")
    if op in {"add", "mul"} and len(args) < 2:
        raise ValueError(
            "POOL_DOCUMENT_POLICY_MAPPING_INVALID: derived expression args must contain at least 2 items"
        )
    if op in {"sub", "div"} and len(args) != 2:
        raise ValueError(
            "POOL_DOCUMENT_POLICY_MAPPING_INVALID: derived expression args must contain exactly 2 items"
        )

    resolved_args: list[Decimal] = []
    for index, raw_arg in enumerate(args):
        resolved_value, is_resolved = _resolve_mapping_value(
            raw_arg,
            allocation=allocation,
            resolved_link_refs=resolved_link_refs,
        )
        if not is_resolved:
            raise ValueError(
                "POOL_DOCUMENT_POLICY_MAPPING_INVALID: derived expression argument "
                f"{index} could not be resolved"
            )
        decimal_value = _parse_decimal(resolved_value)
        if decimal_value is None:
            raise ValueError(
                "POOL_DOCUMENT_POLICY_MAPPING_INVALID: derived expression argument "
                f"{index} must resolve to decimal"
            )
        resolved_args.append(decimal_value)

    result: Decimal
    if op == "add":
        result = sum(resolved_args, Decimal("0"))
    elif op == "sub":
        result = resolved_args[0] - resolved_args[1]
    elif op == "mul":
        result = Decimal("1")
        for item in resolved_args:
            result *= item
    else:
        if resolved_args[1] == 0:
            raise ValueError("POOL_DOCUMENT_POLICY_MAPPING_INVALID: derived expression division by zero")
        result = resolved_args[0] / resolved_args[1]

    if "scale" in expression:
        scale = expression.get("scale")
        if not isinstance(scale, int) or isinstance(scale, bool) or scale < 0:
            raise ValueError(
                "POOL_DOCUMENT_POLICY_MAPPING_INVALID: derived expression scale must be a non-negative integer"
            )
        result = result.quantize(
            Decimal("1").scaleb(-scale),
            rounding=ROUND_HALF_UP,
        )

    return _decimal_to_string(result), True


def _resolve_dotted_path(payload: Mapping[str, Any], path: str) -> tuple[Any, bool]:
    current: Any = payload
    for segment in path.split("."):
        key = str(segment or "").strip()
        if not key or not isinstance(current, Mapping) or key not in current:
            return None, False
        current = current.get(key)
    return current, True


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _decimal_to_string(value: Decimal) -> str:
    return format(value, "f")
