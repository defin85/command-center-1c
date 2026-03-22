from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from uuid import UUID, uuid4

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from .models import Organization, TopologyTemplate, TopologyTemplateRevision, TopologyTemplateStatus
from .topology_template_contract import (
    POOL_TOPOLOGY_TEMPLATE_INSTANTIATION_METADATA_KEY,
    TOPOLOGY_TEMPLATE_REVISION_CONTRACT_VERSION,
    normalize_topology_template_edge_selector_overrides,
    normalize_topology_template_revision_payload,
    normalize_topology_template_slot_assignments,
)


class TopologyTemplateStoreError(Exception):
    def __init__(self, *, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class MaterializedTopologyTemplateInstantiation:
    revision: TopologyTemplateRevision
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    metadata: dict[str, Any]


def list_topology_templates(*, tenant_id: UUID | str, include_inactive: bool = False) -> list[TopologyTemplate]:
    queryset = (
        TopologyTemplate.objects.filter(tenant_id=tenant_id)
        .prefetch_related("revisions")
        .order_by("code")
    )
    if not include_inactive:
        queryset = queryset.filter(status=TopologyTemplateStatus.ACTIVE)
    return list(queryset)


def create_topology_template(
    *,
    tenant_id: UUID | str,
    code: str,
    name: str,
    description: str = "",
    metadata: dict[str, Any] | None = None,
    revision: dict[str, Any],
    actor_username: str = "",
) -> TopologyTemplate:
    nodes, edges = _normalize_revision_payload(revision=revision)
    template_metadata = _normalize_optional_metadata_mapping(
        metadata,
        field_name="metadata",
    )
    revision_metadata = _normalize_optional_metadata_mapping(
        revision.get("metadata"),
        field_name="revision.metadata",
    )
    with transaction.atomic():
        template = TopologyTemplate.objects.create(
            tenant_id=tenant_id,
            code=code,
            name=name,
            description=description,
            metadata=template_metadata,
            created_by=actor_username,
            updated_by=actor_username,
        )
        _create_topology_template_revision(
            template=template,
            nodes=nodes,
            edges=edges,
            metadata=revision_metadata,
            actor_username=actor_username,
        )
    return template


def create_topology_template_revision(
    *,
    tenant_id: UUID | str,
    topology_template_id: UUID | str,
    revision: dict[str, Any],
    actor_username: str = "",
) -> TopologyTemplateRevision:
    template = TopologyTemplate.objects.filter(
        id=topology_template_id,
        tenant_id=tenant_id,
    ).first()
    if template is None:
        raise TopologyTemplateStoreError(
            code="TOPOLOGY_TEMPLATE_NOT_FOUND",
            detail="Topology template not found in current tenant context.",
        )
    nodes, edges = _normalize_revision_payload(revision=revision)
    return _create_topology_template_revision(
        template=template,
        nodes=nodes,
        edges=edges,
        metadata=_normalize_optional_metadata_mapping(
            revision.get("metadata"),
            field_name="revision.metadata",
        ),
        actor_username=actor_username,
    )


def get_topology_template_revision(
    *,
    tenant_id: UUID | str,
    topology_template_revision_id: str,
) -> TopologyTemplateRevision:
    revision = (
        TopologyTemplateRevision.objects.select_related("template")
        .filter(
            tenant_id=tenant_id,
            topology_template_revision_id=str(topology_template_revision_id or "").strip(),
        )
        .first()
    )
    if revision is None:
        raise TopologyTemplateStoreError(
            code="TOPOLOGY_TEMPLATE_REVISION_NOT_FOUND",
            detail="Topology template revision not found in current tenant context.",
        )
    return revision


def materialize_topology_template_instantiation(
    *,
    tenant_id: UUID | str,
    topology_template_revision_id: str,
    slot_assignments: Any,
    edge_selector_overrides: Any,
) -> MaterializedTopologyTemplateInstantiation:
    revision = get_topology_template_revision(
        tenant_id=tenant_id,
        topology_template_revision_id=topology_template_revision_id,
    )
    if revision.template.status != TopologyTemplateStatus.ACTIVE:
        raise TopologyTemplateStoreError(
            code="TOPOLOGY_TEMPLATE_INACTIVE",
            detail="Topology template is inactive and cannot be used for new instantiation.",
        )

    template_nodes = list(revision.nodes if isinstance(revision.nodes, list) else [])
    template_edges = list(revision.edges if isinstance(revision.edges, list) else [])
    expected_slot_keys = [str(node.get("slot_key") or "").strip() for node in template_nodes]
    expected_edges = [
        (
            str(edge.get("parent_slot_key") or "").strip(),
            str(edge.get("child_slot_key") or "").strip(),
        )
        for edge in template_edges
    ]

    try:
        normalized_assignments = normalize_topology_template_slot_assignments(
            slot_assignments=slot_assignments,
            expected_slot_keys=expected_slot_keys,
        )
        normalized_overrides = normalize_topology_template_edge_selector_overrides(
            edge_selector_overrides=edge_selector_overrides,
            expected_edges=expected_edges,
        )
    except DjangoValidationError as exc:
        raise TopologyTemplateStoreError(
            code="VALIDATION_ERROR",
            detail=_validation_message(exc),
        ) from exc

    organizations = {
        str(item.id): item
        for item in Organization.objects.filter(
            id__in=[assignment["organization_id"] for assignment in normalized_assignments],
            tenant_id=tenant_id,
        )
    }
    missing_organization_ids = sorted(
        {assignment["organization_id"] for assignment in normalized_assignments} - set(organizations)
    )
    if missing_organization_ids:
        raise TopologyTemplateStoreError(
            code="ORGANIZATION_NOT_FOUND",
            detail=(
                "Organizations not found in tenant context: "
                + ", ".join(missing_organization_ids)
            ),
        )

    organization_id_by_slot_key = {
        assignment["slot_key"]: assignment["organization_id"]
        for assignment in normalized_assignments
    }
    override_by_edge = {
        (override["parent_slot_key"], override["child_slot_key"]): override["document_policy_key"]
        for override in normalized_overrides
    }

    nodes: list[dict[str, Any]] = []
    for node in template_nodes:
        slot_key = str(node.get("slot_key") or "").strip()
        organization_id = organization_id_by_slot_key[slot_key]
        nodes.append(
            {
                "organization_id": organization_id,
                "is_root": bool(node.get("is_root", False)),
                "metadata": dict(node.get("metadata") or {}),
            }
        )

    edges: list[dict[str, Any]] = []
    for edge in template_edges:
        parent_slot_key = str(edge.get("parent_slot_key") or "").strip()
        child_slot_key = str(edge.get("child_slot_key") or "").strip()
        metadata = dict(edge.get("metadata") or {})
        document_policy_key = override_by_edge.get(
            (parent_slot_key, child_slot_key),
            str(edge.get("document_policy_key") or "").strip() or None,
        )
        metadata.pop("document_policy_key", None)
        if document_policy_key:
            metadata["document_policy_key"] = document_policy_key
        edges.append(
            {
                "parent_organization_id": organization_id_by_slot_key[parent_slot_key],
                "child_organization_id": organization_id_by_slot_key[child_slot_key],
                "weight": str(edge.get("weight") or "1"),
                "min_amount": edge.get("min_amount"),
                "max_amount": edge.get("max_amount"),
                "metadata": metadata,
            }
        )

    return MaterializedTopologyTemplateInstantiation(
        revision=revision,
        nodes=nodes,
        edges=edges,
        metadata={
            POOL_TOPOLOGY_TEMPLATE_INSTANTIATION_METADATA_KEY: {
                "topology_template_id": str(revision.template_id),
                "topology_template_code": revision.template.code,
                "topology_template_name": revision.template.name,
                "topology_template_revision_id": revision.topology_template_revision_id,
                "topology_template_revision_number": revision.revision_number,
                "slot_assignments": normalized_assignments,
                "edge_selector_overrides": normalized_overrides,
            }
        },
    )


def serialize_topology_template(template: TopologyTemplate) -> dict[str, Any]:
    revisions = sorted(
        list(template.revisions.all()),
        key=lambda item: item.revision_number,
        reverse=True,
    )
    latest_revision = revisions[0] if revisions else None
    return {
        "topology_template_id": str(template.id),
        "code": template.code,
        "name": template.name,
        "description": template.description,
        "status": template.status,
        "metadata": template.metadata if isinstance(template.metadata, dict) else {},
        "latest_revision_number": latest_revision.revision_number if latest_revision else 0,
        "latest_revision": serialize_topology_template_revision(latest_revision) if latest_revision else None,
        "revisions": [serialize_topology_template_revision(item) for item in revisions],
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


def serialize_topology_template_revision(revision: TopologyTemplateRevision | None) -> dict[str, Any] | None:
    if revision is None:
        return None
    return {
        "topology_template_revision_id": revision.topology_template_revision_id,
        "topology_template_id": str(revision.template_id),
        "revision_number": revision.revision_number,
        "nodes": list(revision.nodes if isinstance(revision.nodes, list) else []),
        "edges": list(revision.edges if isinstance(revision.edges, list) else []),
        "metadata": revision.metadata if isinstance(revision.metadata, dict) else {},
        "created_at": revision.created_at,
    }


def _create_topology_template_revision(
    *,
    template: TopologyTemplate,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    metadata: dict[str, Any],
    actor_username: str,
) -> TopologyTemplateRevision:
    latest_revision = (
        TopologyTemplateRevision.objects.filter(template=template)
        .order_by("-revision_number")
        .first()
    )
    revision_number = (latest_revision.revision_number if latest_revision else 0) + 1
    revision = TopologyTemplateRevision.objects.create(
        topology_template_revision_id=f"topology-template-revision-{uuid4().hex}",
        tenant_id=template.tenant_id,
        template=template,
        contract_version=TOPOLOGY_TEMPLATE_REVISION_CONTRACT_VERSION,
        revision_number=revision_number,
        nodes=nodes,
        edges=edges,
        metadata=metadata,
        created_by=actor_username,
    )
    if actor_username and template.updated_by != actor_username:
        template.updated_by = actor_username
        template.save(update_fields=["updated_by", "updated_at"])
    return revision


def _normalize_revision_payload(*, revision: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        return normalize_topology_template_revision_payload(
            nodes=revision.get("nodes"),
            edges=revision.get("edges"),
        )
    except DjangoValidationError as exc:
        raise TopologyTemplateStoreError(
            code="VALIDATION_ERROR",
            detail=_validation_message(exc),
        ) from exc


def _validation_message(exc: DjangoValidationError) -> str:
    if hasattr(exc, "message_dict"):
        return str(exc.message_dict)
    if hasattr(exc, "messages"):
        return "; ".join(str(message) for message in exc.messages)
    return str(exc)


def _normalize_optional_metadata_mapping(
    value: Any,
    *,
    field_name: str,
) -> dict[str, Any]:
    if value is None or value == "":
        return {}
    if not isinstance(value, Mapping):
        raise TopologyTemplateStoreError(
            code="VALIDATION_ERROR",
            detail=f"{field_name} must be an object.",
        )
    return dict(value)
