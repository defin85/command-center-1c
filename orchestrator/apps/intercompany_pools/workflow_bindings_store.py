from __future__ import annotations

from typing import Any, Iterable
from uuid import uuid4

from apps.intercompany_pools.models import OrganizationPool, PoolWorkflowBinding
from apps.intercompany_pools.workflow_authoring_contract import PoolWorkflowBindingContract
from apps.intercompany_pools.workflow_binding_resolution import parse_pool_workflow_bindings


class PoolWorkflowBindingStoreError(ValueError):
    pass


class PoolWorkflowBindingNotFoundError(PoolWorkflowBindingStoreError):
    def __init__(self, *, binding_id: str) -> None:
        super().__init__(f"Pool workflow binding '{binding_id}' was not found.")
        self.binding_id = binding_id


def list_canonical_pool_workflow_bindings(*, pool: OrganizationPool) -> list[dict[str, Any]]:
    records = PoolWorkflowBinding.objects.filter(pool=pool).order_by("effective_from", "created_at", "binding_id")
    return [_serialize_canonical_record(record) for record in records]


def get_canonical_pool_workflow_binding(*, pool: OrganizationPool, binding_id: str) -> dict[str, Any]:
    record = PoolWorkflowBinding.objects.filter(pool=pool, binding_id=binding_id).first()
    if record is None:
        raise PoolWorkflowBindingNotFoundError(binding_id=binding_id)
    return _serialize_canonical_record(record)


def upsert_canonical_pool_workflow_binding(
    *,
    pool: OrganizationPool,
    workflow_binding: dict[str, Any],
    actor_username: str = "",
) -> tuple[dict[str, Any], bool]:
    payload = dict(workflow_binding)
    binding_id = str(payload.get("binding_id") or "").strip() or str(uuid4())
    payload["binding_id"] = binding_id
    payload["pool_id"] = str(pool.id)

    try:
        contract = PoolWorkflowBindingContract(**payload)
    except Exception as exc:
        raise PoolWorkflowBindingStoreError(str(exc)) from exc

    actor = str(actor_username or "").strip()
    existing = PoolWorkflowBinding.objects.filter(pool=pool, binding_id=contract.binding_id).first()
    if existing is None:
        record = PoolWorkflowBinding.objects.create(
            binding_id=contract.binding_id,
            tenant=pool.tenant,
            pool=pool,
            contract_version=contract.contract_version,
            status=contract.status.value,
            effective_from=contract.effective_from,
            effective_to=contract.effective_to,
            direction=contract.selector.direction or "",
            mode=contract.selector.mode or "",
            selector_tags=list(contract.selector.tags),
            workflow_definition_key=contract.workflow.workflow_definition_key,
            workflow_revision_id=contract.workflow.workflow_revision_id,
            workflow_revision=contract.workflow.workflow_revision,
            workflow_name=contract.workflow.workflow_name,
            decisions=[decision.model_dump(mode="json") for decision in contract.decisions],
            parameters=dict(contract.parameters),
            role_mapping=dict(contract.role_mapping),
            revision=1,
            created_by=actor,
            updated_by=actor,
        )
        return _serialize_canonical_record(record), True

    existing.contract_version = contract.contract_version
    existing.status = contract.status.value
    existing.effective_from = contract.effective_from
    existing.effective_to = contract.effective_to
    existing.direction = contract.selector.direction or ""
    existing.mode = contract.selector.mode or ""
    existing.selector_tags = list(contract.selector.tags)
    existing.workflow_definition_key = contract.workflow.workflow_definition_key
    existing.workflow_revision_id = contract.workflow.workflow_revision_id
    existing.workflow_revision = contract.workflow.workflow_revision
    existing.workflow_name = contract.workflow.workflow_name
    existing.decisions = [decision.model_dump(mode="json") for decision in contract.decisions]
    existing.parameters = dict(contract.parameters)
    existing.role_mapping = dict(contract.role_mapping)
    existing.revision += 1
    existing.updated_by = actor
    existing.save()
    return _serialize_canonical_record(existing), False


def extract_pool_workflow_bindings(metadata: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(metadata, dict):
        return []
    raw = metadata.get("workflow_bindings")
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def normalize_pool_workflow_bindings_for_storage(
    *,
    pool_id: str,
    workflow_bindings: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized_bindings: list[dict[str, Any]] = []
    seen_binding_ids: set[str] = set()

    for index, binding in enumerate(workflow_bindings, start=1):
        payload = dict(binding)
        provided_pool_id = str(payload.get("pool_id") or "").strip()
        if provided_pool_id and provided_pool_id != pool_id:
            raise PoolWorkflowBindingStoreError(
                f"binding #{index}: pool_id must match enclosing pool id"
            )

        binding_id = str(payload.get("binding_id") or "").strip() or str(uuid4())
        if binding_id in seen_binding_ids:
            raise PoolWorkflowBindingStoreError(
                f"binding #{index}: binding_id must be unique"
            )
        seen_binding_ids.add(binding_id)

        payload["binding_id"] = binding_id
        payload["pool_id"] = pool_id

        try:
            contract = PoolWorkflowBindingContract(**payload)
        except Exception as exc:
            raise PoolWorkflowBindingStoreError(str(exc)) from exc

        normalized_bindings.append(contract.model_dump(mode="json"))

    return normalized_bindings


def list_pool_workflow_bindings(*, pool: OrganizationPool) -> list[dict[str, Any]]:
    metadata = pool.metadata if isinstance(pool.metadata, dict) else {}
    bindings = parse_pool_workflow_bindings(extract_pool_workflow_bindings(metadata))
    return [binding.model_dump(mode="json") for binding in bindings]


def get_pool_workflow_binding(*, pool: OrganizationPool, binding_id: str) -> dict[str, Any]:
    for binding in list_pool_workflow_bindings(pool=pool):
        if str(binding.get("binding_id") or "").strip() == binding_id:
            return binding
    raise PoolWorkflowBindingNotFoundError(binding_id=binding_id)


def upsert_pool_workflow_binding(
    *,
    pool: OrganizationPool,
    workflow_binding: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    metadata = dict(pool.metadata) if isinstance(pool.metadata, dict) else {}
    existing_bindings = extract_pool_workflow_bindings(metadata)
    normalized_payload = dict(workflow_binding)
    binding_id = str(normalized_payload.get("binding_id") or "").strip() or str(uuid4())
    normalized_payload["binding_id"] = binding_id
    normalized_payload["pool_id"] = str(pool.id)

    stored_bindings: list[dict[str, Any]] = []
    replaced = False
    for current in existing_bindings:
        current_binding_id = str(current.get("binding_id") or "").strip()
        if current_binding_id == binding_id:
            stored_bindings.append(normalized_payload)
            replaced = True
            continue
        stored_bindings.append(dict(current))
    if not replaced:
        stored_bindings.append(normalized_payload)

    normalized_bindings = normalize_pool_workflow_bindings_for_storage(
        pool_id=str(pool.id),
        workflow_bindings=stored_bindings,
    )
    metadata = _with_stored_workflow_bindings(metadata=metadata, bindings=normalized_bindings)
    pool.metadata = metadata
    pool.save(update_fields=["metadata", "updated_at"])

    created = not replaced
    saved_binding = next(
        binding
        for binding in normalized_bindings
        if str(binding.get("binding_id") or "").strip() == binding_id
    )
    return saved_binding, created


def delete_pool_workflow_binding(*, pool: OrganizationPool, binding_id: str) -> dict[str, Any]:
    metadata = dict(pool.metadata) if isinstance(pool.metadata, dict) else {}
    existing_bindings = extract_pool_workflow_bindings(metadata)
    stored_bindings: list[dict[str, Any]] = []
    removed_binding: dict[str, Any] | None = None

    for current in existing_bindings:
        current_binding_id = str(current.get("binding_id") or "").strip()
        if current_binding_id == binding_id:
            removed_binding = dict(current)
            continue
        stored_bindings.append(dict(current))

    if removed_binding is None:
        raise PoolWorkflowBindingNotFoundError(binding_id=binding_id)

    normalized_bindings = normalize_pool_workflow_bindings_for_storage(
        pool_id=str(pool.id),
        workflow_bindings=stored_bindings,
    )
    metadata = _with_stored_workflow_bindings(metadata=metadata, bindings=normalized_bindings)
    pool.metadata = metadata
    pool.save(update_fields=["metadata", "updated_at"])
    return PoolWorkflowBindingContract(**removed_binding).model_dump(mode="json")


def _with_stored_workflow_bindings(
    *,
    metadata: dict[str, Any],
    bindings: list[dict[str, Any]],
) -> dict[str, Any]:
    updated_metadata = dict(metadata)
    if bindings:
        updated_metadata["workflow_bindings"] = bindings
    else:
        updated_metadata["workflow_bindings"] = []
    return updated_metadata


def _serialize_canonical_record(record: PoolWorkflowBinding) -> dict[str, Any]:
    contract = PoolWorkflowBindingContract(
        contract_version=record.contract_version,
        binding_id=record.binding_id,
        pool_id=str(record.pool_id),
        workflow={
            "workflow_definition_key": record.workflow_definition_key,
            "workflow_revision_id": record.workflow_revision_id,
            "workflow_revision": record.workflow_revision,
            "workflow_name": record.workflow_name,
        },
        decisions=list(record.decisions),
        parameters=dict(record.parameters),
        role_mapping=dict(record.role_mapping),
        selector={
            "direction": record.direction,
            "mode": record.mode,
            "tags": list(record.selector_tags),
        },
        effective_from=record.effective_from,
        effective_to=record.effective_to,
        status=record.status,
    )
    return contract.model_dump(mode="json")


__all__ = [
    "PoolWorkflowBindingNotFoundError",
    "PoolWorkflowBindingStoreError",
    "delete_pool_workflow_binding",
    "extract_pool_workflow_bindings",
    "get_canonical_pool_workflow_binding",
    "get_pool_workflow_binding",
    "list_canonical_pool_workflow_bindings",
    "list_pool_workflow_bindings",
    "normalize_pool_workflow_bindings_for_storage",
    "upsert_canonical_pool_workflow_binding",
    "upsert_pool_workflow_binding",
]
