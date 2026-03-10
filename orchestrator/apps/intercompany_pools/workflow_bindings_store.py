from __future__ import annotations

from typing import Any, Iterable
from uuid import uuid4

from django.db import transaction

from apps.intercompany_pools.models import OrganizationPool, PoolWorkflowBinding
from apps.intercompany_pools.workflow_authoring_contract import PoolWorkflowBindingContract


class PoolWorkflowBindingStoreError(ValueError):
    pass


class PoolWorkflowBindingNotFoundError(PoolWorkflowBindingStoreError):
    def __init__(self, *, binding_id: str) -> None:
        super().__init__(f"Pool workflow binding '{binding_id}' was not found.")
        self.binding_id = binding_id


class PoolWorkflowBindingRevisionConflictError(PoolWorkflowBindingStoreError):
    def __init__(
        self,
        *,
        binding_id: str,
        expected_revision: int,
        actual_revision: int,
        operation: str,
    ) -> None:
        super().__init__(
            "Pool workflow binding revision conflict: "
            f"binding_id='{binding_id}', operation='{operation}', "
            f"expected_revision={expected_revision}, actual_revision={actual_revision}"
        )
        self.binding_id = binding_id
        self.expected_revision = expected_revision
        self.actual_revision = actual_revision
        self.operation = operation


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
    requested_revision = _normalize_requested_revision(
        payload.pop("revision", None),
        required=False,
        operation="update",
    )
    binding_id = str(payload.get("binding_id") or "").strip() or str(uuid4())
    payload["binding_id"] = binding_id
    payload["pool_id"] = str(pool.id)

    try:
        contract = PoolWorkflowBindingContract(**payload)
    except Exception as exc:
        raise PoolWorkflowBindingStoreError(str(exc)) from exc

    actor = str(actor_username or "").strip()
    with transaction.atomic():
        existing = (
            PoolWorkflowBinding.objects.select_for_update()
            .filter(pool=pool, binding_id=contract.binding_id)
            .first()
        )
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

        if requested_revision is None:
            raise PoolWorkflowBindingStoreError("revision is required for update")
        if requested_revision != existing.revision:
            raise PoolWorkflowBindingRevisionConflictError(
                binding_id=contract.binding_id,
                expected_revision=requested_revision,
                actual_revision=existing.revision,
                operation="update",
            )

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


def delete_canonical_pool_workflow_binding(
    *,
    pool: OrganizationPool,
    binding_id: str,
    revision: int | None = None,
) -> dict[str, Any]:
    requested_revision = _normalize_requested_revision(
        revision,
        required=True,
        operation="delete",
    )
    with transaction.atomic():
        record = (
            PoolWorkflowBinding.objects.select_for_update()
            .filter(pool=pool, binding_id=binding_id)
            .first()
        )
        if record is None:
            raise PoolWorkflowBindingNotFoundError(binding_id=binding_id)
        if requested_revision != record.revision:
            raise PoolWorkflowBindingRevisionConflictError(
                binding_id=binding_id,
                expected_revision=requested_revision,
                actual_revision=record.revision,
                operation="delete",
            )
        serialized = _serialize_canonical_record(record)
        record.delete()
        return serialized


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
    return list_canonical_pool_workflow_bindings(pool=pool)


def get_pool_workflow_binding(*, pool: OrganizationPool, binding_id: str) -> dict[str, Any]:
    return get_canonical_pool_workflow_binding(pool=pool, binding_id=binding_id)


def upsert_pool_workflow_binding(
    *,
    pool: OrganizationPool,
    workflow_binding: dict[str, Any],
    actor_username: str = "",
) -> tuple[dict[str, Any], bool]:
    return upsert_canonical_pool_workflow_binding(
        pool=pool,
        workflow_binding=workflow_binding,
        actor_username=actor_username,
    )


def delete_pool_workflow_binding(
    *,
    pool: OrganizationPool,
    binding_id: str,
    revision: int | None = None,
) -> dict[str, Any]:
    return delete_canonical_pool_workflow_binding(pool=pool, binding_id=binding_id, revision=revision)


def _normalize_requested_revision(
    raw_revision: object,
    *,
    required: bool,
    operation: str,
) -> int | None:
    if raw_revision is None or raw_revision == "":
        if required:
            raise PoolWorkflowBindingStoreError(f"revision is required for {operation}")
        return None
    if isinstance(raw_revision, bool):
        raise PoolWorkflowBindingStoreError(f"revision must be a positive integer for {operation}")
    try:
        normalized = int(raw_revision)
    except (TypeError, ValueError) as exc:
        raise PoolWorkflowBindingStoreError(
            f"revision must be a positive integer for {operation}"
        ) from exc
    if normalized < 1:
        raise PoolWorkflowBindingStoreError(f"revision must be a positive integer for {operation}")
    return normalized

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
    return {
        **contract.model_dump(mode="json"),
        "revision": record.revision,
    }


__all__ = [
    "PoolWorkflowBindingNotFoundError",
    "PoolWorkflowBindingRevisionConflictError",
    "PoolWorkflowBindingStoreError",
    "delete_canonical_pool_workflow_binding",
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
