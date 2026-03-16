from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable
from uuid import uuid4

from django.db import transaction

from apps.intercompany_pools.models import OrganizationPool, PoolWorkflowBinding
from apps.intercompany_pools.workflow_authoring_contract import (
    PoolWorkflowBindingContract,
    PoolWorkflowBindingDecisionRef,
)


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


class PoolWorkflowBindingCollectionConflictError(PoolWorkflowBindingStoreError):
    def __init__(
        self,
        *,
        expected_collection_etag: str,
        actual_collection_etag: str,
    ) -> None:
        super().__init__(
            "Pool workflow binding collection conflict: "
            f"expected_collection_etag='{expected_collection_etag}', "
            f"actual_collection_etag='{actual_collection_etag}'"
        )
        self.expected_collection_etag = expected_collection_etag
        self.actual_collection_etag = actual_collection_etag


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
                decisions=_serialize_decision_refs(contract.decisions),
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
        existing.decisions = _serialize_decision_refs(contract.decisions)
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


def get_canonical_pool_workflow_binding_collection(*, pool: OrganizationPool) -> dict[str, Any]:
    bindings = list_canonical_pool_workflow_bindings(pool=pool)
    return _serialize_canonical_collection(pool=pool, bindings=bindings)


def replace_canonical_pool_workflow_bindings_collection(
    *,
    pool: OrganizationPool,
    expected_collection_etag: str,
    workflow_bindings: Iterable[dict[str, Any]],
    actor_username: str = "",
) -> dict[str, Any]:
    normalized_expected_collection_etag = str(expected_collection_etag or "").strip()
    if not normalized_expected_collection_etag:
        raise PoolWorkflowBindingStoreError("expected_collection_etag is required for atomic replace")

    normalized_bindings = normalize_pool_workflow_bindings_for_storage(
        pool_id=str(pool.id),
        workflow_bindings=workflow_bindings,
    )
    actor = str(actor_username or "").strip()

    with transaction.atomic():
        existing_records = list(
            PoolWorkflowBinding.objects.select_for_update()
            .filter(pool=pool)
            .order_by("effective_from", "created_at", "binding_id")
        )
        actual_collection_etag = _calculate_collection_etag(
            [_serialize_canonical_record(record) for record in existing_records]
        )
        if normalized_expected_collection_etag != actual_collection_etag:
            raise PoolWorkflowBindingCollectionConflictError(
                expected_collection_etag=normalized_expected_collection_etag,
                actual_collection_etag=actual_collection_etag,
            )

        existing_by_id = {record.binding_id: record for record in existing_records}
        next_binding_ids: set[str] = set()

        for normalized_binding in normalized_bindings:
            contract = PoolWorkflowBindingContract(**normalized_binding)
            binding_id = contract.binding_id
            if binding_id is None:
                raise PoolWorkflowBindingStoreError("binding_id is required after normalization")
            next_binding_ids.add(binding_id)
            existing = existing_by_id.get(binding_id)
            if existing is None:
                PoolWorkflowBinding.objects.create(
                    binding_id=binding_id,
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
                    decisions=_serialize_decision_refs(contract.decisions),
                    parameters=dict(contract.parameters),
                    role_mapping=dict(contract.role_mapping),
                    revision=1,
                    created_by=actor,
                    updated_by=actor,
                )
                continue

            if _record_matches_contract(existing=existing, contract=contract):
                continue

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
            existing.decisions = _serialize_decision_refs(contract.decisions)
            existing.parameters = dict(contract.parameters)
            existing.role_mapping = dict(contract.role_mapping)
            existing.revision += 1
            existing.updated_by = actor
            existing.save()

        PoolWorkflowBinding.objects.filter(pool=pool).exclude(binding_id__in=next_binding_ids).delete()

    return get_canonical_pool_workflow_binding_collection(pool=pool)


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

        normalized_bindings.append(contract.model_dump(mode="json", exclude_none=True))

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


def get_pool_workflow_binding_collection(*, pool: OrganizationPool) -> dict[str, Any]:
    return get_canonical_pool_workflow_binding_collection(pool=pool)


def replace_pool_workflow_bindings_collection(
    *,
    pool: OrganizationPool,
    expected_collection_etag: str,
    workflow_bindings: Iterable[dict[str, Any]],
    actor_username: str = "",
) -> dict[str, Any]:
    return replace_canonical_pool_workflow_bindings_collection(
        pool=pool,
        expected_collection_etag=expected_collection_etag,
        workflow_bindings=workflow_bindings,
        actor_username=actor_username,
    )


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
        **contract.model_dump(mode="json", exclude_none=True),
        "revision": record.revision,
    }


def _record_matches_contract(
    *,
    existing: PoolWorkflowBinding,
    contract: PoolWorkflowBindingContract,
) -> bool:
    return (
        existing.contract_version == contract.contract_version
        and existing.status == contract.status.value
        and existing.effective_from == contract.effective_from
        and existing.effective_to == contract.effective_to
        and existing.direction == (contract.selector.direction or "")
        and existing.mode == (contract.selector.mode or "")
        and list(existing.selector_tags) == list(contract.selector.tags)
        and existing.workflow_definition_key == contract.workflow.workflow_definition_key
        and existing.workflow_revision_id == contract.workflow.workflow_revision_id
        and existing.workflow_revision == contract.workflow.workflow_revision
        and existing.workflow_name == contract.workflow.workflow_name
        and _normalize_stored_decision_refs(existing.decisions) == _serialize_decision_refs(contract.decisions)
        and dict(existing.parameters) == dict(contract.parameters)
        and dict(existing.role_mapping) == dict(contract.role_mapping)
    )


def _serialize_decision_refs(
    decisions: list[PoolWorkflowBindingDecisionRef],
) -> list[dict[str, Any]]:
    return [decision.model_dump(mode="json", exclude_none=True) for decision in decisions]


def _normalize_stored_decision_refs(
    decisions: object,
) -> list[dict[str, Any]]:
    if not isinstance(decisions, list):
        return []
    normalized: list[dict[str, Any]] = []
    for decision in decisions:
        if not isinstance(decision, dict):
            continue
        normalized.append(
            PoolWorkflowBindingDecisionRef(**decision).model_dump(mode="json", exclude_none=True)
        )
    return normalized


def _serialize_canonical_collection(
    *,
    pool: OrganizationPool,
    bindings: list[dict[str, Any]],
) -> dict[str, Any]:
    response = {
        "pool_id": str(pool.id),
        "workflow_bindings": bindings,
        "collection_etag": _calculate_collection_etag(bindings),
    }
    if not bindings and extract_pool_workflow_bindings(pool.metadata):
        response["blocking_remediation"] = {
            "code": "LEGACY_METADATA_WORKFLOW_BINDINGS_PRESENT",
            "title": "Legacy workflow bindings remediation required",
            "detail": (
                "Canonical binding collection is empty while legacy pool.metadata.workflow_bindings "
                "payload is still present. Run explicit remediation before using the default workspace."
            ),
        }
    return response


def _calculate_collection_etag(bindings: list[dict[str, Any]]) -> str:
    normalized = json.dumps(bindings, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(normalized.encode('utf-8')).hexdigest()}"


__all__ = [
    "PoolWorkflowBindingCollectionConflictError",
    "PoolWorkflowBindingNotFoundError",
    "PoolWorkflowBindingRevisionConflictError",
    "PoolWorkflowBindingStoreError",
    "delete_canonical_pool_workflow_binding",
    "delete_pool_workflow_binding",
    "extract_pool_workflow_bindings",
    "get_canonical_pool_workflow_binding_collection",
    "get_canonical_pool_workflow_binding",
    "get_pool_workflow_binding_collection",
    "get_pool_workflow_binding",
    "list_canonical_pool_workflow_bindings",
    "list_pool_workflow_bindings",
    "normalize_pool_workflow_bindings_for_storage",
    "replace_canonical_pool_workflow_bindings_collection",
    "replace_pool_workflow_bindings_collection",
    "upsert_canonical_pool_workflow_binding",
    "upsert_pool_workflow_binding",
]
