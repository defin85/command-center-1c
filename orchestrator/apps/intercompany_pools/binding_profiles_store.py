from __future__ import annotations

from typing import Any
from uuid import uuid4

from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.utils import timezone

from apps.intercompany_pools.binding_profiles_contract import (
    BindingProfileCreateContract,
    BindingProfileRevisionContract,
)
from apps.intercompany_pools.binding_profile_usage_store import build_binding_profile_usage_summary
from apps.intercompany_pools.models import BindingProfile, BindingProfileRevision
from apps.tenancy.models import Tenant


class BindingProfileStoreError(ValueError):
    pass


class BindingProfileNotFoundError(BindingProfileStoreError):
    def __init__(self, *, binding_profile_id: str) -> None:
        super().__init__(f"Binding profile '{binding_profile_id}' was not found.")
        self.binding_profile_id = binding_profile_id


class BindingProfileCodeConflictError(BindingProfileStoreError):
    def __init__(self, *, code: str) -> None:
        super().__init__(f"Binding profile code conflict: code='{code}'")
        self.code = code


class BindingProfileLifecycleConflictError(BindingProfileStoreError):
    def __init__(self, *, binding_profile_id: str, operation: str, status: str) -> None:
        super().__init__(
            "Binding profile lifecycle conflict: "
            f"binding_profile_id='{binding_profile_id}', operation='{operation}', status='{status}'"
        )
        self.binding_profile_id = binding_profile_id
        self.operation = operation
        self.status = status


def list_canonical_binding_profiles(*, tenant: Tenant) -> list[dict[str, Any]]:
    profiles = list(
        BindingProfile.objects.filter(tenant=tenant)
        .prefetch_related(
            Prefetch(
                "revisions",
                queryset=BindingProfileRevision.objects.order_by("-revision_number"),
                to_attr="prefetched_revisions",
            )
        )
        .order_by("-updated_at", "code")
    )
    return [_serialize_binding_profile_summary(profile) for profile in profiles]


def get_canonical_binding_profile(*, tenant: Tenant, binding_profile_id: str) -> dict[str, Any]:
    profile = (
        BindingProfile.objects.filter(tenant=tenant, id=binding_profile_id)
        .prefetch_related(
            Prefetch(
                "revisions",
                queryset=BindingProfileRevision.objects.order_by("-revision_number"),
                to_attr="prefetched_revisions",
            )
        )
        .first()
    )
    if profile is None:
        raise BindingProfileNotFoundError(binding_profile_id=binding_profile_id)
    detail = _serialize_binding_profile_detail(profile)
    detail["usage_summary"] = build_binding_profile_usage_summary(
        tenant=tenant,
        binding_profile_id=str(profile.id),
    )
    return detail


def create_canonical_binding_profile(
    *,
    tenant: Tenant,
    binding_profile: dict[str, Any],
    actor_username: str = "",
) -> dict[str, Any]:
    try:
        contract = BindingProfileCreateContract(**dict(binding_profile))
    except Exception as exc:
        raise BindingProfileStoreError(str(exc)) from exc

    actor = str(actor_username or "").strip()
    try:
        with transaction.atomic():
            profile = BindingProfile.objects.create(
                tenant=tenant,
                code=contract.code,
                name=contract.name,
                description=contract.description,
                created_by=actor,
                updated_by=actor,
            )
            _create_revision_record(
                profile=profile,
                contract=contract.revision,
                revision_number=1,
                actor_username=actor,
            )
    except IntegrityError as exc:
        raise BindingProfileCodeConflictError(code=contract.code) from exc

    return get_canonical_binding_profile(tenant=tenant, binding_profile_id=str(profile.id))


def revise_canonical_binding_profile(
    *,
    tenant: Tenant,
    binding_profile_id: str,
    revision: dict[str, Any],
    actor_username: str = "",
) -> dict[str, Any]:
    try:
        revision_contract = BindingProfileRevisionContract(**dict(revision))
    except Exception as exc:
        raise BindingProfileStoreError(str(exc)) from exc

    actor = str(actor_username or "").strip()
    with transaction.atomic():
        profile = (
            BindingProfile.objects.select_for_update()
            .filter(tenant=tenant, id=binding_profile_id)
            .first()
        )
        if profile is None:
            raise BindingProfileNotFoundError(binding_profile_id=binding_profile_id)
        if profile.status != "active":
            raise BindingProfileLifecycleConflictError(
                binding_profile_id=binding_profile_id,
                operation="revise",
                status=profile.status,
            )

        latest_revision = (
            BindingProfileRevision.objects.filter(profile=profile)
            .order_by("-revision_number")
            .first()
        )
        next_revision_number = (latest_revision.revision_number if latest_revision is not None else 0) + 1
        _create_revision_record(
            profile=profile,
            contract=revision_contract,
            revision_number=next_revision_number,
            actor_username=actor,
        )
        profile.updated_by = actor
        profile.save(update_fields=["updated_by", "updated_at"])

    return get_canonical_binding_profile(tenant=tenant, binding_profile_id=binding_profile_id)


def deactivate_canonical_binding_profile(
    *,
    tenant: Tenant,
    binding_profile_id: str,
    actor_username: str = "",
) -> dict[str, Any]:
    actor = str(actor_username or "").strip()
    with transaction.atomic():
        profile = (
            BindingProfile.objects.select_for_update()
            .filter(tenant=tenant, id=binding_profile_id)
            .first()
        )
        if profile is None:
            raise BindingProfileNotFoundError(binding_profile_id=binding_profile_id)
        if profile.status != "deactivated":
            profile.status = "deactivated"
            profile.deactivated_by = actor
            profile.deactivated_at = timezone.now()
            profile.updated_by = actor
            profile.save(update_fields=["status", "deactivated_by", "deactivated_at", "updated_by", "updated_at"])

    return get_canonical_binding_profile(tenant=tenant, binding_profile_id=binding_profile_id)


def _create_revision_record(
    *,
    profile: BindingProfile,
    contract: BindingProfileRevisionContract,
    revision_number: int,
    actor_username: str,
) -> BindingProfileRevision:
    return BindingProfileRevision.objects.create(
        binding_profile_revision_id=_build_binding_profile_revision_id(),
        tenant=profile.tenant,
        profile=profile,
        contract_version=contract.contract_version,
        revision_number=revision_number,
        workflow_definition_key=contract.workflow.workflow_definition_key,
        workflow_revision_id=contract.workflow.workflow_revision_id,
        workflow_revision=contract.workflow.workflow_revision,
        workflow_name=contract.workflow.workflow_name,
        decisions=_serialize_decision_refs(contract.decisions),
        parameters=dict(contract.parameters),
        role_mapping=dict(contract.role_mapping),
        metadata=dict(contract.metadata),
        created_by=actor_username,
    )


def _build_binding_profile_revision_id() -> str:
    return f"bp_rev_{uuid4().hex}"


def _serialize_binding_profile_summary(profile: BindingProfile) -> dict[str, Any]:
    revisions = _get_prefetched_revisions(profile)
    latest_revision = revisions[0]
    return {
        "binding_profile_id": str(profile.id),
        "code": profile.code,
        "name": profile.name,
        "description": profile.description,
        "status": profile.status,
        "latest_revision_number": latest_revision.revision_number,
        "latest_revision": _serialize_revision(latest_revision),
        "created_by": profile.created_by,
        "updated_by": profile.updated_by,
        "deactivated_by": profile.deactivated_by,
        "deactivated_at": _serialize_datetime(profile.deactivated_at),
        "created_at": _serialize_datetime(profile.created_at),
        "updated_at": _serialize_datetime(profile.updated_at),
    }


def _serialize_binding_profile_detail(profile: BindingProfile) -> dict[str, Any]:
    revisions = _get_prefetched_revisions(profile)
    summary = _serialize_binding_profile_summary(profile)
    summary["revisions"] = [_serialize_revision(revision) for revision in revisions]
    return summary


def _get_prefetched_revisions(profile: BindingProfile) -> list[BindingProfileRevision]:
    revisions = getattr(profile, "prefetched_revisions", None)
    if revisions is None:
        revisions = list(profile.revisions.order_by("-revision_number"))
    if not revisions:
        raise BindingProfileStoreError(f"Binding profile '{profile.id}' has no revisions.")
    return revisions


def _serialize_revision(revision: BindingProfileRevision) -> dict[str, Any]:
    return {
        "contract_version": revision.contract_version,
        "binding_profile_revision_id": revision.binding_profile_revision_id,
        "binding_profile_id": str(revision.profile_id),
        "revision_number": revision.revision_number,
        "workflow": {
            "workflow_definition_key": revision.workflow_definition_key,
            "workflow_revision_id": revision.workflow_revision_id,
            "workflow_revision": revision.workflow_revision,
            "workflow_name": revision.workflow_name,
        },
        "decisions": list(revision.decisions) if isinstance(revision.decisions, list) else [],
        "parameters": dict(revision.parameters) if isinstance(revision.parameters, dict) else {},
        "role_mapping": dict(revision.role_mapping) if isinstance(revision.role_mapping, dict) else {},
        "metadata": dict(revision.metadata) if isinstance(revision.metadata, dict) else {},
        "created_by": revision.created_by,
        "created_at": _serialize_datetime(revision.created_at),
    }


def _serialize_decision_refs(decisions: list[Any]) -> list[dict[str, Any]]:
    return [
        decision.model_dump(mode="json", exclude_none=True)
        if hasattr(decision, "model_dump")
        else dict(decision)
        for decision in decisions
    ]


def _serialize_datetime(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()


__all__ = [
    "BindingProfileCodeConflictError",
    "BindingProfileLifecycleConflictError",
    "BindingProfileNotFoundError",
    "BindingProfileStoreError",
    "create_canonical_binding_profile",
    "deactivate_canonical_binding_profile",
    "get_canonical_binding_profile",
    "list_canonical_binding_profiles",
    "revise_canonical_binding_profile",
]
