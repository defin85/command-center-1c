from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone

from apps.intercompany_pools.models import (
    PoolMasterGLAccount,
    PoolMasterGLAccountSet,
    PoolMasterGLAccountSetDraftMember,
    PoolMasterGLAccountSetRevision,
    PoolMasterGLAccountSetRevisionMember,
)
from apps.tenancy.models import Tenant


class GLAccountSetStoreError(ValueError):
    pass


class GLAccountSetNotFoundError(GLAccountSetStoreError):
    def __init__(self, *, gl_account_set_id: str) -> None:
        super().__init__(f"GLAccountSet '{gl_account_set_id}' was not found.")
        self.gl_account_set_id = gl_account_set_id


class GLAccountSetCanonicalConflictError(GLAccountSetStoreError):
    def __init__(self, *, canonical_id: str) -> None:
        super().__init__(f"GLAccountSet canonical_id conflict: canonical_id='{canonical_id}'")
        self.canonical_id = canonical_id


class GLAccountSetMemberResolutionError(GLAccountSetStoreError):
    def __init__(self, *, errors: list[dict[str, Any]]) -> None:
        super().__init__("GLAccountSet members are invalid for the requested draft state.")
        self.errors = errors


def list_canonical_gl_account_sets(*, tenant: Tenant) -> list[dict[str, Any]]:
    profiles = list(
        PoolMasterGLAccountSet.objects.filter(tenant=tenant)
        .select_related("published_revision")
        .prefetch_related(
            Prefetch(
                "draft_members",
                queryset=PoolMasterGLAccountSetDraftMember.objects.select_related("gl_account").order_by(
                    "sort_order",
                    "created_at",
                ),
                to_attr="prefetched_draft_members",
            )
        )
        .order_by("-updated_at", "canonical_id")
    )
    return [_serialize_gl_account_set_summary(profile) for profile in profiles]


def get_canonical_gl_account_set(*, tenant: Tenant, gl_account_set_id: str) -> dict[str, Any]:
    profile = (
        PoolMasterGLAccountSet.objects.filter(tenant=tenant, id=gl_account_set_id)
        .select_related("published_revision")
        .prefetch_related(
            Prefetch(
                "draft_members",
                queryset=PoolMasterGLAccountSetDraftMember.objects.select_related("gl_account").order_by(
                    "sort_order",
                    "created_at",
                ),
                to_attr="prefetched_draft_members",
            ),
            Prefetch(
                "revisions",
                queryset=PoolMasterGLAccountSetRevision.objects.order_by("-revision_number").prefetch_related(
                    Prefetch(
                        "members",
                        queryset=PoolMasterGLAccountSetRevisionMember.objects.select_related("gl_account").order_by(
                            "sort_order",
                            "created_at",
                        ),
                        to_attr="prefetched_members",
                    )
                ),
                to_attr="prefetched_revisions",
            ),
        )
        .first()
    )
    if profile is None:
        raise GLAccountSetNotFoundError(gl_account_set_id=gl_account_set_id)
    return _serialize_gl_account_set_detail(profile)


def upsert_canonical_gl_account_set(
    *,
    tenant: Tenant,
    gl_account_set: Mapping[str, Any],
    actor_username: str = "",
) -> tuple[dict[str, Any], bool]:
    payload = dict(gl_account_set)
    gl_account_set_id = str(payload.get("gl_account_set_id") or "").strip()
    canonical_id = str(payload.get("canonical_id") or "").strip()
    name = str(payload.get("name") or "").strip()
    description = str(payload.get("description") or "").strip()
    chart_identity = str(payload.get("chart_identity") or "").strip()
    config_name = str(payload.get("config_name") or "").strip()
    config_version = str(payload.get("config_version") or "").strip()
    metadata = _require_object(payload.get("metadata"), field_name="metadata", default={})
    members = _normalize_gl_account_set_members(payload.get("members"))
    actor = str(actor_username or "").strip()

    with transaction.atomic():
        profile = None
        if gl_account_set_id:
            profile = (
                PoolMasterGLAccountSet.objects.select_for_update()
                .filter(tenant=tenant, id=gl_account_set_id)
                .first()
            )
            if profile is None:
                raise GLAccountSetNotFoundError(gl_account_set_id=gl_account_set_id)
        else:
            profile = (
                PoolMasterGLAccountSet.objects.select_for_update()
                .filter(tenant=tenant, canonical_id=canonical_id)
                .first()
            )

        conflicting = (
            PoolMasterGLAccountSet.objects.select_for_update()
            .filter(tenant=tenant, canonical_id=canonical_id)
            .exclude(id=getattr(profile, "id", None))
            .first()
        )
        if conflicting is not None:
            raise GLAccountSetCanonicalConflictError(canonical_id=canonical_id)

        created = profile is None
        if created:
            profile = PoolMasterGLAccountSet.objects.create(
                tenant=tenant,
                canonical_id=canonical_id,
                name=name,
                description=description,
                chart_identity=chart_identity,
                config_name=config_name,
                config_version=config_version,
                metadata=metadata,
            )
        else:
            assert profile is not None
            changed_fields: list[str] = []
            for field_name, new_value in (
                ("canonical_id", canonical_id),
                ("name", name),
                ("description", description),
                ("chart_identity", chart_identity),
                ("config_name", config_name),
                ("config_version", config_version),
                ("metadata", metadata),
            ):
                if getattr(profile, field_name) != new_value:
                    setattr(profile, field_name, new_value)
                    changed_fields.append(field_name)
            if changed_fields:
                profile.updated_at = timezone.now()
                profile.save(update_fields=[*changed_fields, "updated_at"])

        assert profile is not None
        accounts_by_canonical = _resolve_member_accounts(
            tenant=tenant,
            members=members,
            chart_identity=profile.chart_identity,
            config_name=profile.config_name,
            config_version=profile.config_version,
        )
        _replace_draft_members(
            profile=profile,
            tenant=tenant,
            members=members,
            accounts_by_canonical=accounts_by_canonical,
        )
        profile.updated_at = timezone.now()
        profile.save(update_fields=["updated_at"])

    return get_canonical_gl_account_set(tenant=tenant, gl_account_set_id=str(profile.id)), created


def publish_canonical_gl_account_set(
    *,
    tenant: Tenant,
    gl_account_set_id: str,
    actor_username: str = "",
) -> dict[str, Any]:
    actor = str(actor_username or "").strip()
    with transaction.atomic():
        profile = (
            PoolMasterGLAccountSet.objects.select_for_update()
            .filter(tenant=tenant, id=gl_account_set_id)
            .first()
        )
        if profile is None:
            raise GLAccountSetNotFoundError(gl_account_set_id=gl_account_set_id)

        draft_members = list(
            PoolMasterGLAccountSetDraftMember.objects.select_related("gl_account")
            .filter(profile=profile)
            .order_by("sort_order", "created_at")
        )
        latest_revision = (
            PoolMasterGLAccountSetRevision.objects.filter(profile=profile)
            .order_by("-revision_number")
            .first()
        )
        next_revision_number = (latest_revision.revision_number if latest_revision is not None else 0) + 1
        revision = PoolMasterGLAccountSetRevision.objects.create(
            gl_account_set_revision_id=_build_gl_account_set_revision_id(),
            tenant=tenant,
            profile=profile,
            revision_number=next_revision_number,
            name=profile.name,
            description=profile.description,
            chart_identity=profile.chart_identity,
            config_name=profile.config_name,
            config_version=profile.config_version,
            metadata=dict(profile.metadata or {}),
            created_by=actor,
        )
        for draft_member in draft_members:
            account = draft_member.gl_account
            PoolMasterGLAccountSetRevisionMember.objects.create(
                tenant=tenant,
                revision=revision,
                gl_account=account,
                gl_account_canonical_id=str(account.canonical_id),
                gl_account_code=str(account.code),
                gl_account_name=str(account.name),
                chart_identity=str(account.chart_identity),
                sort_order=int(draft_member.sort_order),
                metadata=dict(draft_member.metadata or {}),
            )
        profile.published_revision = revision
        profile.updated_at = timezone.now()
        profile.save(update_fields=["published_revision", "updated_at"])

    return get_canonical_gl_account_set(tenant=tenant, gl_account_set_id=gl_account_set_id)


def _build_gl_account_set_revision_id() -> str:
    return f"gl_account_set_rev_{uuid4().hex}"


def _normalize_gl_account_set_members(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise GLAccountSetStoreError("members must be an array.")
    normalized: list[dict[str, Any]] = []
    seen_canonical_ids: set[str] = set()
    for index, raw_member in enumerate(value):
        if not isinstance(raw_member, Mapping):
            raise GLAccountSetStoreError("Each GLAccountSet member must be an object.")
        canonical_id = str(raw_member.get("canonical_id") or "").strip()
        if not canonical_id:
            raise GLAccountSetStoreError("Each GLAccountSet member must define canonical_id.")
        if canonical_id in seen_canonical_ids:
            raise GLAccountSetStoreError(f"Duplicate GLAccountSet member canonical_id '{canonical_id}'.")
        seen_canonical_ids.add(canonical_id)
        normalized.append(
            {
                "canonical_id": canonical_id,
                "sort_order": index,
                "metadata": _require_object(raw_member.get("metadata"), field_name="member.metadata", default={}),
            }
        )
    return normalized


def _resolve_member_accounts(
    *,
    tenant: Tenant,
    members: list[dict[str, Any]],
    chart_identity: str,
    config_name: str,
    config_version: str,
) -> dict[str, PoolMasterGLAccount]:
    canonical_ids = [str(member["canonical_id"]) for member in members]
    accounts = {
        str(account.canonical_id): account
        for account in PoolMasterGLAccount.objects.filter(
            tenant=tenant,
            canonical_id__in=canonical_ids,
        )
    }
    errors: list[dict[str, Any]] = []
    for member in members:
        canonical_id = str(member["canonical_id"])
        account = accounts.get(canonical_id)
        if account is None:
            errors.append(
                {
                    "code": "GL_ACCOUNT_NOT_FOUND",
                    "canonical_id": canonical_id,
                    "detail": f"GLAccount '{canonical_id}' is not available in tenant scope.",
                }
            )
            continue
        if account.chart_identity != chart_identity:
            errors.append(
                {
                    "code": "GL_ACCOUNT_CHART_IDENTITY_MISMATCH",
                    "canonical_id": canonical_id,
                    "detail": f"GLAccount '{canonical_id}' chart_identity does not match GLAccountSet draft.",
                }
            )
        if account.config_name != config_name:
            errors.append(
                {
                    "code": "GL_ACCOUNT_CONFIG_NAME_MISMATCH",
                    "canonical_id": canonical_id,
                    "detail": f"GLAccount '{canonical_id}' config_name does not match GLAccountSet draft.",
                }
            )
        if account.config_version != config_version:
            errors.append(
                {
                    "code": "GL_ACCOUNT_CONFIG_VERSION_MISMATCH",
                    "canonical_id": canonical_id,
                    "detail": f"GLAccount '{canonical_id}' config_version does not match GLAccountSet draft.",
                }
            )
    if errors:
        raise GLAccountSetMemberResolutionError(errors=errors)
    return accounts


def _replace_draft_members(
    *,
    profile: PoolMasterGLAccountSet,
    tenant: Tenant,
    members: list[dict[str, Any]],
    accounts_by_canonical: Mapping[str, PoolMasterGLAccount],
) -> None:
    PoolMasterGLAccountSetDraftMember.objects.filter(profile=profile).delete()
    for member in members:
        canonical_id = str(member["canonical_id"])
        PoolMasterGLAccountSetDraftMember.objects.create(
            tenant=tenant,
            profile=profile,
            gl_account=accounts_by_canonical[canonical_id],
            sort_order=int(member["sort_order"]),
            metadata=dict(member.get("metadata") or {}),
        )


def _serialize_gl_account_set_summary(profile: PoolMasterGLAccountSet) -> dict[str, Any]:
    published_revision = profile.published_revision
    draft_members = _get_prefetched_draft_members(profile)
    return {
        "gl_account_set_id": str(profile.id),
        "canonical_id": profile.canonical_id,
        "name": profile.name,
        "description": profile.description,
        "chart_identity": profile.chart_identity,
        "config_name": profile.config_name,
        "config_version": profile.config_version,
        "draft_members_count": len(draft_members),
        "published_revision_number": (
            published_revision.revision_number if published_revision is not None else None
        ),
        "published_revision_id": (
            published_revision.gl_account_set_revision_id if published_revision is not None else None
        ),
        "metadata": dict(profile.metadata) if isinstance(profile.metadata, dict) else {},
        "created_at": _serialize_datetime(profile.created_at),
        "updated_at": _serialize_datetime(profile.updated_at),
    }


def _serialize_gl_account_set_detail(profile: PoolMasterGLAccountSet) -> dict[str, Any]:
    detail = _serialize_gl_account_set_summary(profile)
    detail["draft_members"] = [
        _serialize_draft_member(member) for member in _get_prefetched_draft_members(profile)
    ]
    revisions = _get_prefetched_revisions(profile)
    detail["revisions"] = [_serialize_revision(revision) for revision in revisions]
    published_revision = profile.published_revision
    detail["published_revision"] = (
        _serialize_revision(published_revision) if published_revision is not None else None
    )
    return detail


def _get_prefetched_draft_members(profile: PoolMasterGLAccountSet) -> list[PoolMasterGLAccountSetDraftMember]:
    members = getattr(profile, "prefetched_draft_members", None)
    if members is None:
        return list(profile.draft_members.select_related("gl_account").order_by("sort_order", "created_at"))
    return list(members)


def _get_prefetched_revisions(profile: PoolMasterGLAccountSet) -> list[PoolMasterGLAccountSetRevision]:
    revisions = getattr(profile, "prefetched_revisions", None)
    if revisions is None:
        return list(
            profile.revisions.order_by("-revision_number").prefetch_related(
                Prefetch(
                    "members",
                    queryset=PoolMasterGLAccountSetRevisionMember.objects.select_related("gl_account").order_by(
                        "sort_order",
                        "created_at",
                    ),
                    to_attr="prefetched_members",
                )
            )
        )
    return list(revisions)


def _serialize_draft_member(member: PoolMasterGLAccountSetDraftMember) -> dict[str, Any]:
    account = member.gl_account
    return {
        "gl_account_id": str(account.id),
        "canonical_id": str(account.canonical_id),
        "code": str(account.code),
        "name": str(account.name),
        "chart_identity": str(account.chart_identity),
        "config_name": str(account.config_name),
        "config_version": str(account.config_version),
        "sort_order": int(member.sort_order),
        "metadata": dict(member.metadata) if isinstance(member.metadata, dict) else {},
    }


def _serialize_revision(revision: PoolMasterGLAccountSetRevision) -> dict[str, Any]:
    members = getattr(revision, "prefetched_members", None)
    if members is None:
        members = list(revision.members.select_related("gl_account").order_by("sort_order", "created_at"))
    return {
        "gl_account_set_revision_id": revision.gl_account_set_revision_id,
        "gl_account_set_id": str(revision.profile_id),
        "contract_version": revision.contract_version,
        "revision_number": int(revision.revision_number),
        "name": revision.name,
        "description": revision.description,
        "chart_identity": revision.chart_identity,
        "config_name": revision.config_name,
        "config_version": revision.config_version,
        "members": [_serialize_revision_member(member) for member in members],
        "metadata": dict(revision.metadata) if isinstance(revision.metadata, dict) else {},
        "created_by": revision.created_by,
        "created_at": _serialize_datetime(revision.created_at),
    }


def _serialize_revision_member(member: PoolMasterGLAccountSetRevisionMember) -> dict[str, Any]:
    return {
        "gl_account_id": str(member.gl_account_id),
        "canonical_id": str(member.gl_account_canonical_id),
        "code": str(member.gl_account_code),
        "name": str(member.gl_account_name),
        "chart_identity": str(member.chart_identity),
        "sort_order": int(member.sort_order),
        "metadata": dict(member.metadata) if isinstance(member.metadata, dict) else {},
    }


def _require_object(value: Any, *, field_name: str, default: dict[str, Any]) -> dict[str, Any]:
    if value is None:
        return dict(default)
    if not isinstance(value, Mapping):
        raise GLAccountSetStoreError(f"{field_name} must be an object.")
    return dict(value)


def _serialize_datetime(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
