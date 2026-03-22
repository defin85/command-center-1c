from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable
from uuid import uuid4

from django.db import transaction

from apps.intercompany_pools.models import (
    BindingProfile,
    BindingProfileRevision,
    OrganizationPool,
    PoolWorkflowBinding,
)
from apps.intercompany_pools.workflow_binding_attachments_contract import (
    POOL_WORKFLOW_BINDING_ATTACHMENT_CONTRACT_VERSION,
    PoolWorkflowBindingAttachmentContract,
)
from apps.intercompany_pools.workflow_bindings_store import (
    PoolWorkflowBindingCollectionConflictError,
    PoolWorkflowBindingNotFoundError,
    PoolWorkflowBindingRevisionConflictError,
    PoolWorkflowBindingStoreError,
    extract_pool_workflow_bindings,
)


class PoolWorkflowBindingAttachmentLifecycleConflictError(PoolWorkflowBindingStoreError):
    def __init__(
        self,
        *,
        binding_profile_revision_id: str,
        profile_status: str,
        operation: str,
    ) -> None:
        super().__init__(
            "Pool workflow binding profile lifecycle conflict: "
            f"binding_profile_revision_id='{binding_profile_revision_id}', "
            f"profile_status='{profile_status}', operation='{operation}'"
        )
        self.binding_profile_revision_id = binding_profile_revision_id
        self.profile_status = profile_status
        self.operation = operation


POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING = "POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING"


def list_pool_workflow_binding_attachments(*, pool: OrganizationPool) -> list[dict[str, Any]]:
    records = (
        PoolWorkflowBinding.objects.filter(pool=pool)
        .select_related("binding_profile", "binding_profile_revision")
        .order_by("effective_from", "created_at", "binding_id")
    )
    return [_serialize_attachment_record(record) for record in records]


def get_pool_workflow_binding_attachment(*, pool: OrganizationPool, binding_id: str) -> dict[str, Any]:
    record = (
        PoolWorkflowBinding.objects.filter(pool=pool, binding_id=binding_id)
        .select_related("binding_profile", "binding_profile_revision")
        .first()
    )
    if record is None:
        raise PoolWorkflowBindingNotFoundError(binding_id=binding_id)
    return _serialize_attachment_record(record)


def upsert_pool_workflow_binding_attachment(
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
        contract = PoolWorkflowBindingAttachmentContract(**payload)
    except Exception as exc:
        raise PoolWorkflowBindingStoreError(str(exc)) from exc

    actor = str(actor_username or "").strip()
    with transaction.atomic():
        existing = (
            PoolWorkflowBinding.objects.select_for_update()
            .filter(pool=pool, binding_id=contract.binding_id)
            .first()
        )
        profile_revision = _resolve_profile_revision_for_attachment(
            pool=pool,
            binding_profile_revision_id=contract.binding_profile_revision_id,
            existing=existing,
            operation="update" if existing is not None else "create",
        )

        if existing is None:
            record = PoolWorkflowBinding.objects.create(
                binding_id=contract.binding_id,
                tenant=pool.tenant,
                pool=pool,
                binding_profile=profile_revision.profile,
                binding_profile_revision=profile_revision,
                contract_version=contract.contract_version,
                status=contract.status.value,
                effective_from=contract.effective_from,
                effective_to=contract.effective_to,
                direction=contract.selector.direction or "",
                mode=contract.selector.mode or "",
                selector_tags=list(contract.selector.tags),
                workflow_definition_key=profile_revision.workflow_definition_key,
                workflow_revision_id=profile_revision.workflow_revision_id,
                workflow_revision=profile_revision.workflow_revision,
                workflow_name=profile_revision.workflow_name,
                decisions=list(profile_revision.decisions) if isinstance(profile_revision.decisions, list) else [],
                parameters=dict(profile_revision.parameters) if isinstance(profile_revision.parameters, dict) else {},
                role_mapping=dict(profile_revision.role_mapping) if isinstance(profile_revision.role_mapping, dict) else {},
                revision=1,
                created_by=actor,
                updated_by=actor,
            )
            return _serialize_attachment_record(record), True

        if requested_revision is None:
            raise PoolWorkflowBindingStoreError("revision is required for update")
        if requested_revision != existing.revision:
            raise PoolWorkflowBindingRevisionConflictError(
                binding_id=contract.binding_id,
                expected_revision=requested_revision,
                actual_revision=existing.revision,
                operation="update",
            )

        if not _record_matches_attachment_contract(
            existing=existing,
            contract=contract,
            profile_revision=profile_revision,
        ):
            existing.binding_profile = profile_revision.profile
            existing.binding_profile_revision = profile_revision
            existing.contract_version = contract.contract_version
            existing.status = contract.status.value
            existing.effective_from = contract.effective_from
            existing.effective_to = contract.effective_to
            existing.direction = contract.selector.direction or ""
            existing.mode = contract.selector.mode or ""
            existing.selector_tags = list(contract.selector.tags)
            existing.workflow_definition_key = profile_revision.workflow_definition_key
            existing.workflow_revision_id = profile_revision.workflow_revision_id
            existing.workflow_revision = profile_revision.workflow_revision
            existing.workflow_name = profile_revision.workflow_name
            existing.decisions = (
                list(profile_revision.decisions)
                if isinstance(profile_revision.decisions, list)
                else []
            )
            existing.parameters = (
                dict(profile_revision.parameters)
                if isinstance(profile_revision.parameters, dict)
                else {}
            )
            existing.role_mapping = (
                dict(profile_revision.role_mapping)
                if isinstance(profile_revision.role_mapping, dict)
                else {}
            )
            existing.revision += 1
            existing.updated_by = actor
            existing.save()

        return _serialize_attachment_record(existing), False


def delete_pool_workflow_binding_attachment(
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
            .select_related("binding_profile", "binding_profile_revision")
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
        serialized = _serialize_attachment_record(record)
        record.delete()
        return serialized


def get_pool_workflow_binding_attachments_collection(*, pool: OrganizationPool) -> dict[str, Any]:
    bindings = list_pool_workflow_binding_attachments(pool=pool)
    return _serialize_attachment_collection(pool=pool, bindings=bindings)


def replace_pool_workflow_binding_attachments_collection(
    *,
    pool: OrganizationPool,
    expected_collection_etag: str,
    workflow_bindings: Iterable[dict[str, Any]],
    actor_username: str = "",
) -> dict[str, Any]:
    normalized_expected_collection_etag = str(expected_collection_etag or "").strip()
    if not normalized_expected_collection_etag:
        raise PoolWorkflowBindingStoreError("expected_collection_etag is required for atomic replace")

    normalized_bindings = normalize_pool_workflow_binding_attachments_for_storage(
        pool_id=str(pool.id),
        workflow_bindings=workflow_bindings,
    )
    actor = str(actor_username or "").strip()

    with transaction.atomic():
        existing_records = list(
            PoolWorkflowBinding.objects.select_for_update()
            .filter(pool=pool)
            .select_related("binding_profile", "binding_profile_revision")
            .order_by("effective_from", "created_at", "binding_id")
        )
        actual_collection_etag = _calculate_collection_etag(
            [_serialize_attachment_record(record) for record in existing_records]
        )
        if normalized_expected_collection_etag != actual_collection_etag:
            raise PoolWorkflowBindingCollectionConflictError(
                expected_collection_etag=normalized_expected_collection_etag,
                actual_collection_etag=actual_collection_etag,
            )

        existing_by_id = {record.binding_id: record for record in existing_records}
        next_binding_ids: set[str] = set()

        for normalized_binding in normalized_bindings:
            contract = PoolWorkflowBindingAttachmentContract(**normalized_binding)
            binding_id = contract.binding_id
            next_binding_ids.add(binding_id)
            existing = existing_by_id.get(binding_id)
            profile_revision = _resolve_profile_revision_for_attachment(
                pool=pool,
                binding_profile_revision_id=contract.binding_profile_revision_id,
                existing=existing,
                operation="replace",
            )

            if existing is None:
                PoolWorkflowBinding.objects.create(
                    binding_id=binding_id,
                    tenant=pool.tenant,
                    pool=pool,
                    binding_profile=profile_revision.profile,
                    binding_profile_revision=profile_revision,
                    contract_version=contract.contract_version,
                    status=contract.status.value,
                    effective_from=contract.effective_from,
                    effective_to=contract.effective_to,
                    direction=contract.selector.direction or "",
                    mode=contract.selector.mode or "",
                    selector_tags=list(contract.selector.tags),
                    workflow_definition_key=profile_revision.workflow_definition_key,
                    workflow_revision_id=profile_revision.workflow_revision_id,
                    workflow_revision=profile_revision.workflow_revision,
                    workflow_name=profile_revision.workflow_name,
                    decisions=list(profile_revision.decisions) if isinstance(profile_revision.decisions, list) else [],
                    parameters=dict(profile_revision.parameters) if isinstance(profile_revision.parameters, dict) else {},
                    role_mapping=dict(profile_revision.role_mapping) if isinstance(profile_revision.role_mapping, dict) else {},
                    revision=1,
                    created_by=actor,
                    updated_by=actor,
                )
                continue

            if _record_matches_attachment_contract(
                existing=existing,
                contract=contract,
                profile_revision=profile_revision,
            ):
                continue

            existing.binding_profile = profile_revision.profile
            existing.binding_profile_revision = profile_revision
            existing.contract_version = contract.contract_version
            existing.status = contract.status.value
            existing.effective_from = contract.effective_from
            existing.effective_to = contract.effective_to
            existing.direction = contract.selector.direction or ""
            existing.mode = contract.selector.mode or ""
            existing.selector_tags = list(contract.selector.tags)
            existing.workflow_definition_key = profile_revision.workflow_definition_key
            existing.workflow_revision_id = profile_revision.workflow_revision_id
            existing.workflow_revision = profile_revision.workflow_revision
            existing.workflow_name = profile_revision.workflow_name
            existing.decisions = list(profile_revision.decisions) if isinstance(profile_revision.decisions, list) else []
            existing.parameters = dict(profile_revision.parameters) if isinstance(profile_revision.parameters, dict) else {}
            existing.role_mapping = dict(profile_revision.role_mapping) if isinstance(profile_revision.role_mapping, dict) else {}
            existing.revision += 1
            existing.updated_by = actor
            existing.save()

        PoolWorkflowBinding.objects.filter(pool=pool).exclude(binding_id__in=next_binding_ids).delete()

    return get_pool_workflow_binding_attachments_collection(pool=pool)


def normalize_pool_workflow_binding_attachments_for_storage(
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
            raise PoolWorkflowBindingStoreError(f"binding #{index}: pool_id must match enclosing pool id")

        binding_id = str(payload.get("binding_id") or "").strip() or str(uuid4())
        if binding_id in seen_binding_ids:
            raise PoolWorkflowBindingStoreError(f"binding #{index}: binding_id must be unique")
        seen_binding_ids.add(binding_id)

        payload["binding_id"] = binding_id
        payload["pool_id"] = pool_id

        try:
            contract = PoolWorkflowBindingAttachmentContract(**payload)
        except Exception as exc:
            raise PoolWorkflowBindingStoreError(str(exc)) from exc

        normalized_bindings.append(contract.model_dump(mode="json", exclude_none=True))

    return normalized_bindings


def _resolve_profile_revision_for_attachment(
    *,
    pool: OrganizationPool,
    binding_profile_revision_id: str,
    existing: PoolWorkflowBinding | None,
    operation: str,
) -> BindingProfileRevision:
    profile_revision = (
        BindingProfileRevision.objects.select_related("profile")
        .filter(tenant=pool.tenant, binding_profile_revision_id=binding_profile_revision_id)
        .first()
    )
    if profile_revision is None:
        raise PoolWorkflowBindingStoreError(
            f"POOL_WORKFLOW_BINDING_PROFILE_REVISION_NOT_FOUND: binding_profile_revision_id '{binding_profile_revision_id}' was not found."
        )
    if profile_revision.profile.status != "active":
        already_pinned = (
            existing is not None
            and existing.binding_profile_revision_id == profile_revision.binding_profile_revision_id
            and existing.binding_profile_id == profile_revision.profile_id
        )
        if not already_pinned:
            raise PoolWorkflowBindingAttachmentLifecycleConflictError(
                binding_profile_revision_id=binding_profile_revision_id,
                profile_status=profile_revision.profile.status,
                operation=operation,
            )
    return profile_revision


def _record_matches_attachment_contract(
    *,
    existing: PoolWorkflowBinding,
    contract: PoolWorkflowBindingAttachmentContract,
    profile_revision: BindingProfileRevision,
) -> bool:
    return (
        existing.contract_version == contract.contract_version
        and existing.status == contract.status.value
        and existing.effective_from == contract.effective_from
        and existing.effective_to == contract.effective_to
        and existing.direction == (contract.selector.direction or "")
        and existing.mode == (contract.selector.mode or "")
        and list(existing.selector_tags) == list(contract.selector.tags)
        and existing.binding_profile_id == profile_revision.profile_id
        and existing.binding_profile_revision_id == profile_revision.binding_profile_revision_id
    )


def _serialize_attachment_record(record: PoolWorkflowBinding) -> dict[str, Any]:
    profile = record.binding_profile
    profile_revision = record.binding_profile_revision
    if profile is None or profile_revision is None:
        raise PoolWorkflowBindingStoreError(
            f"{POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING}: "
            f"Workflow binding '{record.binding_id}' is missing binding_profile references."
        )
    return {
        "contract_version": record.contract_version or POOL_WORKFLOW_BINDING_ATTACHMENT_CONTRACT_VERSION,
        "binding_id": record.binding_id,
        "pool_id": str(record.pool_id),
        "binding_profile_id": str(profile.id),
        "binding_profile_revision_id": profile_revision.binding_profile_revision_id,
        "binding_profile_revision_number": profile_revision.revision_number,
        "selector": {
            "direction": record.direction or None,
            "mode": record.mode or None,
            "tags": list(record.selector_tags),
        },
        "effective_from": record.effective_from.isoformat(),
        "effective_to": record.effective_to.isoformat() if record.effective_to else None,
        "status": record.status,
        "revision": record.revision,
        "resolved_profile": {
            "binding_profile_id": str(profile.id),
            "code": profile.code,
            "name": profile.name,
            "status": profile.status,
            "binding_profile_revision_id": profile_revision.binding_profile_revision_id,
            "binding_profile_revision_number": profile_revision.revision_number,
            "workflow": {
                "workflow_definition_key": profile_revision.workflow_definition_key,
                "workflow_revision_id": profile_revision.workflow_revision_id,
                "workflow_revision": profile_revision.workflow_revision,
                "workflow_name": profile_revision.workflow_name,
            },
            "decisions": list(profile_revision.decisions) if isinstance(profile_revision.decisions, list) else [],
            "parameters": dict(profile_revision.parameters) if isinstance(profile_revision.parameters, dict) else {},
            "role_mapping": dict(profile_revision.role_mapping) if isinstance(profile_revision.role_mapping, dict) else {},
        },
        "profile_lifecycle_warning": _build_profile_lifecycle_warning(profile=profile),
    }


def _build_profile_lifecycle_warning(*, profile: BindingProfile) -> dict[str, str] | None:
    if profile.status == "active":
        return None
    return {
        "code": "BINDING_PROFILE_DEACTIVATED",
        "title": "Binding profile is deactivated",
        "detail": "Pinned reusable binding profile is deactivated and requires planned migration.",
    }


def _serialize_attachment_collection(
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


__all__ = [
    "POOL_WORKFLOW_BINDING_PROFILE_REFS_MISSING",
    "PoolWorkflowBindingAttachmentLifecycleConflictError",
    "delete_pool_workflow_binding_attachment",
    "get_pool_workflow_binding_attachment",
    "get_pool_workflow_binding_attachments_collection",
    "list_pool_workflow_binding_attachments",
    "normalize_pool_workflow_binding_attachments_for_storage",
    "replace_pool_workflow_binding_attachments_collection",
    "upsert_pool_workflow_binding_attachment",
]
