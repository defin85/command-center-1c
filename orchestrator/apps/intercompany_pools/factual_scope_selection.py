from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Mapping
from uuid import uuid4

from django.db import transaction

from apps.databases.models import Database
from apps.databases.odata import (
    ODataQueryAdapter,
    ODataQueryTransportError,
    resolve_database_odata_verify_tls,
)

from .factual_sync_runtime import (
    FACTUAL_SOURCE_PROFILE_SALES_REPORT_V1,
    FactualSalesReportSyncScope,
    build_factual_sales_report_sync_scope,
)
from .models import (
    OrganizationPool,
    PoolFactualScopeSelection,
    PoolMasterDataBinding,
    PoolMasterDataEntityType,
    PoolMasterGLAccount,
    PoolMasterGLAccountSet,
    PoolMasterGLAccountSetDraftMember,
    PoolMasterGLAccountSetRevision,
    PoolMasterGLAccountSetRevisionMember,
)


FACTUAL_SCOPE_CONTRACT_VERSION = "factual_scope_contract.v2"
FACTUAL_SCOPE_SELECTION_MODE_SYSTEM_MANAGED = "system_managed"
DEFAULT_FACTUAL_ACCOUNT_CODES = ("62.01", "90.01")
DEFAULT_FACTUAL_MOVEMENT_KINDS = ("credit", "debit")
DEFAULT_FACTUAL_GL_ACCOUNT_SET_CANONICAL_ID = "factual_sales_report_default"
DEFAULT_FACTUAL_GL_ACCOUNT_SET_NAME = "Factual Sales Report Default"
DEFAULT_FACTUAL_GL_ACCOUNT_SET_DESCRIPTION = "System-managed factual bridge scope for the default sales report cohort."
DEFAULT_FACTUAL_CHART_IDENTITY = "ChartOfAccounts_Хозрасчетный"
DEFAULT_FACTUAL_CONFIG_NAME = "Accounting"
DEFAULT_FACTUAL_CONFIG_VERSION = "3.0"
POOL_FACTUAL_SCOPE_BINDING_MISSING = "POOL_FACTUAL_SCOPE_GL_ACCOUNT_BINDING_MISSING"
POOL_FACTUAL_SCOPE_BINDING_AMBIGUOUS = "POOL_FACTUAL_SCOPE_GL_ACCOUNT_BINDING_AMBIGUOUS"
POOL_FACTUAL_SCOPE_BINDING_STALE = "POOL_FACTUAL_SCOPE_GL_ACCOUNT_BINDING_STALE"
POOL_FACTUAL_SCOPE_LIVE_LOOKUP_FAILED = "POOL_FACTUAL_SCOPE_LIVE_LOOKUP_FAILED"
DEFAULT_FACTUAL_GL_ACCOUNT_DEFINITIONS = (
    {
        "canonical_id": "factual_sales_report_62_01",
        "code": "62.01",
        "name": "62.01",
    },
    {
        "canonical_id": "factual_sales_report_90_01",
        "code": "90.01",
        "name": "90.01",
    },
)


@dataclass(frozen=True)
class FactualScopeSelectionError(ValueError):
    code: str
    detail: str
    scope: FactualSalesReportSyncScope
    blockers: tuple[dict[str, Any], ...]

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


def build_pool_factual_scope_selector_key(
    *,
    pool_id: str,
    quarter_start: date,
    source_profile: str = FACTUAL_SOURCE_PROFILE_SALES_REPORT_V1,
) -> str:
    return f"pool:{pool_id}:{source_profile}:{quarter_start.isoformat()}"


def ensure_pool_factual_scope_selection(
    *,
    pool: OrganizationPool,
    quarter_start: date,
    source_profile: str = FACTUAL_SOURCE_PROFILE_SALES_REPORT_V1,
) -> PoolFactualScopeSelection:
    quarter_end = _resolve_quarter_end(quarter_start)
    with transaction.atomic():
        selection = (
            PoolFactualScopeSelection.objects.select_for_update()
            .select_related("gl_account_set", "gl_account_set_revision")
            .filter(
                tenant=pool.tenant,
                pool=pool,
                source_profile=source_profile,
                quarter_start=quarter_start,
            )
            .first()
        )
        if selection is not None and selection.gl_account_set_id and selection.gl_account_set_revision_id:
            if selection.quarter_end != quarter_end:
                selection.quarter_end = quarter_end
                selection.save(update_fields=["quarter_end", "updated_at"])
            return selection

        gl_account_set, revision = _ensure_default_factual_gl_account_set_revision(pool=pool)
        if selection is None:
            return PoolFactualScopeSelection.objects.create(
                tenant=pool.tenant,
                pool=pool,
                source_profile=source_profile,
                quarter_start=quarter_start,
                quarter_end=quarter_end,
                gl_account_set=gl_account_set,
                gl_account_set_revision=revision,
                selection_mode=FACTUAL_SCOPE_SELECTION_MODE_SYSTEM_MANAGED,
                metadata={
                    "selector_key": build_pool_factual_scope_selector_key(
                        pool_id=str(pool.id),
                        quarter_start=quarter_start,
                        source_profile=source_profile,
                    ),
                    "backfilled_default": True,
                },
            )

        selection.quarter_end = quarter_end
        selection.gl_account_set = gl_account_set
        selection.gl_account_set_revision = revision
        selection.selection_mode = FACTUAL_SCOPE_SELECTION_MODE_SYSTEM_MANAGED
        selection.metadata = {
            **dict(selection.metadata or {}),
            "selector_key": build_pool_factual_scope_selector_key(
                pool_id=str(pool.id),
                quarter_start=quarter_start,
                source_profile=source_profile,
            ),
            "backfilled_default": True,
        }
        selection.save(
            update_fields=[
                "quarter_end",
                "gl_account_set",
                "gl_account_set_revision",
                "selection_mode",
                "metadata",
                "updated_at",
            ]
        )
        return selection


def resolve_pool_factual_sync_scope_for_database(
    *,
    pool: OrganizationPool,
    database: Database,
    quarter_start: date,
    quarter_end: date,
    organization_ids: Iterable[str],
    movement_kinds: Iterable[str] = DEFAULT_FACTUAL_MOVEMENT_KINDS,
    source_profile: str = FACTUAL_SOURCE_PROFILE_SALES_REPORT_V1,
    verify_live_bindings: bool = True,
) -> FactualSalesReportSyncScope:
    selection = ensure_pool_factual_scope_selection(
        pool=pool,
        quarter_start=quarter_start,
        source_profile=source_profile,
    )
    revision = _load_selection_revision(selection=selection)
    effective_members = _serialize_revision_members(revision=revision)
    account_codes = tuple(member["code"] for member in effective_members)
    selector_key = build_pool_factual_scope_selector_key(
        pool_id=str(pool.id),
        quarter_start=quarter_start,
        source_profile=source_profile,
    )
    base_scope = build_factual_sales_report_sync_scope(
        quarter_start=quarter_start,
        quarter_end=quarter_end,
        organization_ids=organization_ids,
        account_codes=account_codes,
        movement_kinds=movement_kinds,
        selector_key=selector_key,
        gl_account_set_id=str(selection.gl_account_set_id),
        gl_account_set_revision_id=str(selection.gl_account_set_revision_id),
        effective_members=effective_members,
        resolved_bindings=(),
        contract_version=FACTUAL_SCOPE_CONTRACT_VERSION,
    )
    resolved_bindings, blockers = _resolve_binding_snapshots(
        database=database,
        revision=revision,
        effective_members=effective_members,
    )
    if blockers:
        raise FactualScopeSelectionError(
            code=POOL_FACTUAL_SCOPE_BINDING_MISSING,
            detail=_build_blocker_summary(blockers=blockers),
            blockers=tuple(blockers),
            scope=base_scope,
        )
    if verify_live_bindings:
        resolved_bindings, live_blockers = _verify_binding_snapshots_live(
            database=database,
            accounting_register_entity=base_scope.accounting_register_entity,
            resolved_bindings=resolved_bindings,
        )
        if live_blockers:
            raise FactualScopeSelectionError(
                code=POOL_FACTUAL_SCOPE_LIVE_LOOKUP_FAILED,
                detail=_build_blocker_summary(blockers=live_blockers),
                blockers=tuple(live_blockers),
                scope=base_scope,
            )
    return build_factual_sales_report_sync_scope(
        quarter_start=quarter_start,
        quarter_end=quarter_end,
        organization_ids=organization_ids,
        account_codes=account_codes,
        movement_kinds=movement_kinds,
        selector_key=selector_key,
        gl_account_set_id=str(selection.gl_account_set_id),
        gl_account_set_revision_id=str(selection.gl_account_set_revision_id),
        effective_members=effective_members,
        resolved_bindings=resolved_bindings,
        contract_version=FACTUAL_SCOPE_CONTRACT_VERSION,
    )


def _ensure_default_factual_gl_account_set_revision(
    *,
    pool: OrganizationPool,
) -> tuple[PoolMasterGLAccountSet, PoolMasterGLAccountSetRevision]:
    tenant = pool.tenant
    accounts = _ensure_default_gl_accounts(tenant=tenant)
    profile_fields = _resolve_profile_compatibility_fields(accounts=accounts)
    profile = (
        PoolMasterGLAccountSet.objects.select_for_update()
        .filter(tenant=tenant, canonical_id=DEFAULT_FACTUAL_GL_ACCOUNT_SET_CANONICAL_ID)
        .first()
    )
    if profile is None:
        profile = PoolMasterGLAccountSet.objects.create(
            tenant=tenant,
            canonical_id=DEFAULT_FACTUAL_GL_ACCOUNT_SET_CANONICAL_ID,
            name=DEFAULT_FACTUAL_GL_ACCOUNT_SET_NAME,
            description=DEFAULT_FACTUAL_GL_ACCOUNT_SET_DESCRIPTION,
            chart_identity=profile_fields["chart_identity"],
            config_name=profile_fields["config_name"],
            config_version=profile_fields["config_version"],
            metadata={"system_managed": True, "factual_default": True},
        )
    else:
        changed_fields: list[str] = []
        for field_name, value in (
            ("name", DEFAULT_FACTUAL_GL_ACCOUNT_SET_NAME),
            ("description", DEFAULT_FACTUAL_GL_ACCOUNT_SET_DESCRIPTION),
            ("chart_identity", profile_fields["chart_identity"]),
            ("config_name", profile_fields["config_name"]),
            ("config_version", profile_fields["config_version"]),
        ):
            if getattr(profile, field_name) != value:
                setattr(profile, field_name, value)
                changed_fields.append(field_name)
        next_metadata = {
            **dict(profile.metadata or {}),
            "system_managed": True,
            "factual_default": True,
        }
        if profile.metadata != next_metadata:
            profile.metadata = next_metadata
            changed_fields.append("metadata")
        if changed_fields:
            profile.save(update_fields=[*changed_fields, "updated_at"])

    _replace_default_profile_draft_members(profile=profile, accounts=accounts)
    published_revision = _resolve_matching_published_revision(profile=profile, accounts=accounts)
    if published_revision is None:
        published_revision = _publish_system_managed_revision(profile=profile, accounts=accounts)
    return profile, published_revision


def _ensure_default_gl_accounts(*, tenant) -> tuple[PoolMasterGLAccount, ...]:
    accounts: list[PoolMasterGLAccount] = []
    for item in DEFAULT_FACTUAL_GL_ACCOUNT_DEFINITIONS:
        account = (
            PoolMasterGLAccount.objects.select_for_update()
            .filter(tenant=tenant, canonical_id=item["canonical_id"])
            .first()
        )
        if account is None:
            account = (
                PoolMasterGLAccount.objects.select_for_update()
                .filter(
                    tenant=tenant,
                    code=item["code"],
                    chart_identity=DEFAULT_FACTUAL_CHART_IDENTITY,
                )
                .order_by("created_at", "id")
                .first()
            )
        if account is None:
            account = PoolMasterGLAccount.objects.create(
                tenant=tenant,
                canonical_id=item["canonical_id"],
                code=item["code"],
                name=item["name"],
                chart_identity=DEFAULT_FACTUAL_CHART_IDENTITY,
                config_name=DEFAULT_FACTUAL_CONFIG_NAME,
                config_version=DEFAULT_FACTUAL_CONFIG_VERSION,
                metadata={
                    "system_managed": True,
                    "factual_default": True,
                },
            )
        accounts.append(account)
    return tuple(accounts)


def _resolve_profile_compatibility_fields(*, accounts: Iterable[PoolMasterGLAccount]) -> dict[str, str]:
    account_list = list(accounts)
    chart_identities = {str(account.chart_identity or "").strip() for account in account_list}
    config_names = {str(account.config_name or "").strip() for account in account_list}
    config_versions = {str(account.config_version or "").strip() for account in account_list}
    if len(chart_identities) != 1 or len(config_names) != 1 or len(config_versions) != 1:
        raise ValueError("Default factual GL accounts must share one compatibility class.")
    return {
        "chart_identity": next(iter(chart_identities)),
        "config_name": next(iter(config_names)),
        "config_version": next(iter(config_versions)),
    }


def _replace_default_profile_draft_members(
    *,
    profile: PoolMasterGLAccountSet,
    accounts: Iterable[PoolMasterGLAccount],
) -> None:
    account_list = list(accounts)
    existing = list(
        PoolMasterGLAccountSetDraftMember.objects.select_for_update()
        .filter(profile=profile)
        .order_by("sort_order", "created_at")
    )
    matches_existing = (
        len(existing) == len(account_list)
        and all(
            existing[index].gl_account_id == account.id and int(existing[index].sort_order) == index
            for index, account in enumerate(account_list)
        )
    )
    if matches_existing:
        return
    if existing:
        PoolMasterGLAccountSetDraftMember.objects.filter(profile=profile).delete()
    for index, account in enumerate(account_list):
        PoolMasterGLAccountSetDraftMember.objects.create(
            tenant=profile.tenant,
            profile=profile,
            gl_account=account,
            sort_order=index,
            metadata={"system_managed": True, "factual_default": True},
        )


def _resolve_matching_published_revision(
    *,
    profile: PoolMasterGLAccountSet,
    accounts: Iterable[PoolMasterGLAccount],
) -> PoolMasterGLAccountSetRevision | None:
    revision = profile.published_revision
    if revision is None:
        return None
    members = list(
        PoolMasterGLAccountSetRevisionMember.objects.filter(revision=revision)
        .order_by("sort_order", "created_at")
        .values_list("gl_account_id", flat=True)
    )
    expected = [account.id for account in accounts]
    if members != expected:
        return None
    return revision


def _publish_system_managed_revision(
    *,
    profile: PoolMasterGLAccountSet,
    accounts: Iterable[PoolMasterGLAccount],
) -> PoolMasterGLAccountSetRevision:
    latest_revision = (
        PoolMasterGLAccountSetRevision.objects.filter(profile=profile)
        .order_by("-revision_number")
        .first()
    )
    revision = PoolMasterGLAccountSetRevision.objects.create(
        gl_account_set_revision_id=f"gl_account_set_rev_{uuid4().hex}",
        tenant=profile.tenant,
        profile=profile,
        revision_number=(latest_revision.revision_number if latest_revision is not None else 0) + 1,
        name=profile.name,
        description=profile.description,
        chart_identity=profile.chart_identity,
        config_name=profile.config_name,
        config_version=profile.config_version,
        metadata={
            **dict(profile.metadata or {}),
            "system_managed": True,
            "factual_default": True,
        },
        created_by="system:factual_scope_bridge",
    )
    for index, account in enumerate(accounts):
        PoolMasterGLAccountSetRevisionMember.objects.create(
            tenant=profile.tenant,
            revision=revision,
            gl_account=account,
            gl_account_canonical_id=str(account.canonical_id or ""),
            gl_account_code=str(account.code or ""),
            gl_account_name=str(account.name or ""),
            chart_identity=str(account.chart_identity or ""),
            sort_order=index,
            metadata={
                "system_managed": True,
                "factual_default": True,
            },
        )
    profile.published_revision = revision
    profile.save(update_fields=["published_revision", "updated_at"])
    return revision


def _load_selection_revision(*, selection: PoolFactualScopeSelection) -> PoolMasterGLAccountSetRevision:
    revision = (
        PoolMasterGLAccountSetRevision.objects.filter(
            gl_account_set_revision_id=selection.gl_account_set_revision_id
        )
        .select_related("profile")
        .prefetch_related("members", "members__gl_account")
        .first()
    )
    if revision is None:
        raise ValueError("Factual scope selection points to a missing GLAccountSet revision.")
    return revision


def _serialize_revision_members(
    *,
    revision: PoolMasterGLAccountSetRevision,
) -> tuple[dict[str, Any], ...]:
    members = list(revision.members.select_related("gl_account").order_by("sort_order", "created_at"))
    return tuple(
        {
            "canonical_id": str(member.gl_account_canonical_id or member.gl_account.canonical_id or ""),
            "code": str(member.gl_account_code or member.gl_account.code or ""),
            "name": str(member.gl_account_name or member.gl_account.name or ""),
            "chart_identity": str(member.chart_identity or revision.chart_identity or ""),
            "sort_order": int(member.sort_order),
        }
        for member in members
    )


def _resolve_binding_snapshots(
    *,
    database: Database,
    revision: PoolMasterGLAccountSetRevision,
    effective_members: Iterable[dict[str, Any]],
) -> tuple[tuple[dict[str, Any], ...], list[dict[str, Any]]]:
    resolved: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    members = list(revision.members.select_related("gl_account").order_by("sort_order", "created_at"))
    members_by_canonical = {
        str(member.gl_account_canonical_id or member.gl_account.canonical_id or ""): member
        for member in members
    }
    for effective_member in effective_members:
        canonical_id = str(effective_member["canonical_id"])
        member = members_by_canonical.get(canonical_id)
        if member is None:
            blockers.append(
                _build_gl_account_blocker(
                    code=POOL_FACTUAL_SCOPE_BINDING_MISSING,
                    detail="Pinned GLAccountSet member is missing from revision payload.",
                    kind="gl_account_member_missing",
                    database=database,
                    effective_member=effective_member,
                )
            )
            continue
        binding_candidates = list(
            PoolMasterDataBinding.objects.filter(
                tenant=database.tenant,
                entity_type=PoolMasterDataEntityType.GL_ACCOUNT,
                canonical_id=canonical_id,
                database=database,
                chart_identity=str(effective_member["chart_identity"]),
            )
            .order_by("created_at", "id")[:2]
        )
        if len(binding_candidates) > 1:
            blockers.append(
                _build_gl_account_blocker(
                    code=POOL_FACTUAL_SCOPE_BINDING_AMBIGUOUS,
                    detail="Multiple GLAccount bindings match the target database and chart scope.",
                    kind="gl_account_binding_ambiguous",
                    database=database,
                    effective_member=effective_member,
                    diagnostic_extra={
                        "binding_ids": [str(item.id) for item in binding_candidates],
                    },
                )
            )
            continue
        target_ref_key = ""
        binding_source = ""
        if binding_candidates:
            target_ref_key = str(binding_candidates[0].ib_ref_key or "").strip()
            binding_source = "binding_table"
        else:
            target_ref_key = _read_gl_account_ib_ref_key_from_metadata(
                metadata=member.gl_account.metadata if isinstance(member.gl_account.metadata, Mapping) else {},
                database_id=str(database.id),
                chart_identity=str(effective_member["chart_identity"]),
            )
            binding_source = "canonical_metadata" if target_ref_key else ""
        if not target_ref_key:
            blockers.append(
                _build_gl_account_blocker(
                    code=POOL_FACTUAL_SCOPE_BINDING_MISSING,
                    detail="Selected GLAccountSet member has no binding coverage for the target database chart.",
                    kind="gl_account_binding_missing",
                    database=database,
                    effective_member=effective_member,
                )
            )
            continue
        resolved.append(
            {
                "canonical_id": canonical_id,
                "code": str(effective_member["code"]),
                "name": str(effective_member["name"]),
                "chart_identity": str(effective_member["chart_identity"]),
                "target_ref_key": target_ref_key,
                "binding_source": binding_source,
            }
        )
    return tuple(resolved), blockers


def _verify_binding_snapshots_live(
    *,
    database: Database,
    accounting_register_entity: str,
    resolved_bindings: Iterable[dict[str, Any]],
) -> tuple[tuple[dict[str, Any], ...], list[dict[str, Any]]]:
    chart_entity = _derive_chart_of_accounts_entity(accounting_register_entity)
    live_refs = _query_chart_ref_map(database=database, chart_entity=chart_entity)
    verified: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for binding in resolved_bindings:
        target_ref_key = str(binding.get("target_ref_key") or "").strip()
        live_code = live_refs.get(target_ref_key, "")
        expected_code = str(binding.get("code") or "").strip()
        if not live_code:
            blockers.append(
                _build_gl_account_blocker(
                    code=POOL_FACTUAL_SCOPE_BINDING_STALE,
                    detail="Pinned GLAccount binding Ref_Key is not present in the target chart of accounts.",
                    kind="gl_account_binding_stale",
                    database=database,
                    effective_member=binding,
                )
            )
            continue
        if expected_code and live_code != expected_code:
            blockers.append(
                _build_gl_account_blocker(
                    code=POOL_FACTUAL_SCOPE_BINDING_STALE,
                    detail="Pinned GLAccount binding Ref_Key resolves to a different account code in the target chart of accounts.",
                    kind="gl_account_binding_stale",
                    database=database,
                    effective_member=binding,
                    diagnostic_extra={
                        "expected_code": expected_code,
                        "live_code": live_code,
                    },
                )
            )
            continue
        verified.append(
            {
                **dict(binding),
                "live_code": live_code,
            }
        )
    return tuple(verified), blockers


def _query_chart_ref_map(
    *,
    database: Database,
    chart_entity: str,
) -> dict[str, str]:
    rows: list[dict[str, Any]] = []
    skip = 0
    with ODataQueryAdapter(
        base_url=str(database.odata_url or ""),
        username=str(database.username or ""),
        password=str(database.password or ""),
        timeout=database.connection_timeout,
        verify_tls=resolve_database_odata_verify_tls(database=database),
    ) as adapter:
        while True:
            try:
                response = adapter.query(
                    entity_name=chart_entity,
                    top=500,
                    skip=skip,
                )
            except ODataQueryTransportError as exc:
                raise ValueError(f"{chart_entity}: {exc}") from exc
            if response.status_code >= 400:
                raise ValueError(f"{chart_entity}: HTTP {response.status_code}")
            payload = response.json()
            page_rows = payload.get("value", []) if isinstance(payload, Mapping) else []
            if not isinstance(page_rows, list):
                raise ValueError(f"{chart_entity}: response payload must contain JSON array 'value'")
            rows.extend(item for item in page_rows if isinstance(item, dict))
            if len(page_rows) < 500:
                break
            skip += len(page_rows)
    return {
        str(row.get("Ref_Key") or row.get("ref_key") or "").strip(): str(row.get("Code") or row.get("code") or "").strip()
        for row in rows
        if str(row.get("Ref_Key") or row.get("ref_key") or "").strip()
    }


def _read_gl_account_ib_ref_key_from_metadata(
    *,
    metadata: Mapping[str, Any],
    database_id: str,
    chart_identity: str,
) -> str:
    ib_ref_keys = metadata.get("ib_ref_keys")
    if not isinstance(ib_ref_keys, Mapping):
        return ""
    database_entry = ib_ref_keys.get(database_id)
    if not isinstance(database_entry, Mapping):
        return ""
    return str(database_entry.get(chart_identity) or database_entry.get("ref") or "").strip()


def _build_gl_account_blocker(
    *,
    code: str,
    detail: str,
    kind: str,
    database: Database,
    effective_member: Mapping[str, Any],
    diagnostic_extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    blocker: dict[str, Any] = {
        "code": code,
        "detail": detail,
        "kind": kind,
        "entity_name": "gl_account",
        "field_or_table_path": str(effective_member.get("canonical_id") or effective_member.get("code") or ""),
        "database_id": str(database.id),
    }
    diagnostic = {
        "canonical_id": str(effective_member.get("canonical_id") or ""),
        "gl_account_code": str(effective_member.get("code") or ""),
        "chart_identity": str(effective_member.get("chart_identity") or ""),
    }
    if diagnostic_extra:
        diagnostic.update(dict(diagnostic_extra))
    blocker["diagnostic"] = diagnostic
    return blocker


def _build_blocker_summary(*, blockers: Iterable[dict[str, Any]]) -> str:
    first = next(iter(blockers), None)
    if first is None:
        return "Factual scope selection failed."
    return str(first.get("detail") or "Factual scope selection failed.")


def _derive_chart_of_accounts_entity(accounting_register_entity: str) -> str:
    normalized = str(accounting_register_entity or "").strip()
    if normalized.startswith("AccountingRegister_"):
        return normalized.replace("AccountingRegister_", "ChartOfAccounts_", 1)
    return DEFAULT_FACTUAL_CHART_IDENTITY


def _resolve_quarter_end(quarter_start: date) -> date:
    if quarter_start.month == 10:
        return date(quarter_start.year + 1, 1, 1).replace(day=1) - date.resolution
    return date(quarter_start.year, quarter_start.month + 3, 1) - date.resolution


__all__ = [
    "DEFAULT_FACTUAL_ACCOUNT_CODES",
    "DEFAULT_FACTUAL_MOVEMENT_KINDS",
    "FACTUAL_SCOPE_CONTRACT_VERSION",
    "FactualScopeSelectionError",
    "build_pool_factual_scope_selector_key",
    "ensure_pool_factual_scope_selection",
    "resolve_pool_factual_sync_scope_for_database",
]
