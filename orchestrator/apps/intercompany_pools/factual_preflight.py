from __future__ import annotations

import json
from datetime import date
from typing import Any, Iterable

from django.utils import timezone

from apps.databases.models import Database
from apps.databases.odata import (
    ODataQueryAdapter,
    ODataQueryTransportError,
    resolve_database_odata_verify_tls,
)

from .business_configuration_profile import get_business_configuration_profile
from .factual_read_boundary import build_factual_odata_read_boundary
from .factual_scope_selection import (
    DEFAULT_FACTUAL_MOVEMENT_KINDS,
    FactualScopeSelectionError,
    resolve_pool_factual_sync_scope_for_database,
)
from .factual_source_profile import REQUIRED_FACTUAL_INFORMATION_REGISTER
from .factual_sync_runtime import resolve_factual_sync_source_state
from .factual_workspace_runtime import resolve_pool_factual_scope
from .metadata_catalog import (
    _fetch_live_catalog_payload,
    describe_metadata_catalog_snapshot_resolution,
    refresh_metadata_catalog_snapshot,
)
from .models import OrganizationPool


DEFAULT_FACTUAL_PREFLIGHT_PAGE_SIZE = 500


class FactualPreflightError(RuntimeError):
    def __init__(self, *, code: str, detail: str) -> None:
        self.code = str(code or "").strip() or "POOL_FACTUAL_PREFLIGHT_FAILED"
        self.detail = str(detail or "").strip() or "factual preflight failed"
        super().__init__(f"{self.code}: {self.detail}")


def run_pool_factual_sync_preflight(
    *,
    pool_id: str,
    quarter_start: date,
    requested_by_username: str = "",
    database_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    pool = OrganizationPool.objects.select_related("tenant").get(id=pool_id)
    scope = resolve_pool_factual_scope(
        pool=pool,
        quarter_start=quarter_start,
        now=timezone.now(),
    )
    selected_database_ids = {str(item).strip() for item in (database_ids or ()) if str(item).strip()}
    databases = tuple(
        database
        for database in scope.databases
        if not selected_database_ids or str(database.id) in selected_database_ids
    )

    if not scope.organization_ids or not databases:
        return {
            "decision": "no_go",
            "pool_id": str(pool.id),
            "pool_code": str(pool.code or ""),
            "tenant_id": str(pool.tenant_id),
            "quarter_start": quarter_start.isoformat(),
            "quarter_end": scope.quarter_end.isoformat(),
            "organization_ids": list(scope.organization_ids),
            "summary": {
                "database_count": 0,
                "failed_databases": 0,
                "go_databases": 0,
            },
            "databases": [],
        }

    database_reports = [
        _run_database_preflight(
            pool=pool,
            database=database,
            quarter_start=quarter_start,
            quarter_end=scope.quarter_end,
            organization_ids=scope.organization_ids,
            requested_by_username=requested_by_username,
        )
        for database in databases
    ]
    failed_databases = sum(1 for item in database_reports if item["decision"] != "go")
    go_databases = len(database_reports) - failed_databases

    return {
        "decision": "go" if failed_databases == 0 else "no_go",
        "pool_id": str(pool.id),
        "pool_code": str(pool.code or ""),
        "tenant_id": str(pool.tenant_id),
        "quarter_start": quarter_start.isoformat(),
        "quarter_end": scope.quarter_end.isoformat(),
        "organization_ids": list(scope.organization_ids),
        "summary": {
            "database_count": len(database_reports),
            "failed_databases": failed_databases,
            "go_databases": go_databases,
        },
        "databases": database_reports,
    }


def _run_database_preflight(
    *,
    pool,
    database: Database,
    quarter_start: date,
    quarter_end: date,
    organization_ids: tuple[str, ...],
    requested_by_username: str,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    source_state = resolve_factual_sync_source_state(database=database)
    scope_contract = None
    source_ok = source_state.state == "available"
    checks.append(
        _check(
            key="source_availability",
            ok=source_ok,
            detail=source_state.detail or source_state.state,
            source_state=source_state.state,
            source_code=source_state.code,
        )
    )

    metadata_snapshot: dict[str, Any] = {}
    live_probe: dict[str, Any] = {}
    if not source_ok:
        checks.append(_skipped_check("published_metadata_refresh", "source is not available for preflight"))
        checks.append(_skipped_check("published_boundary", "published metadata refresh did not run"))
        checks.append(_skipped_check("gl_account_bindings", "published boundary validation did not succeed"))
        checks.append(_skipped_check("bounded_scope", "published boundary validation did not succeed"))
        checks.append(_skipped_check("live_probe", "source availability gate did not pass"))
        return _database_report(
            database=database,
            decision="no_go",
            scope_contract=scope_contract,
            checks=checks,
            source_state=source_state,
            metadata_snapshot=metadata_snapshot,
            live_probe=live_probe,
        )

    snapshot_payload: dict[str, Any] | None = None
    boundary_payload: dict[str, Any] | None = None
    boundary_payload_source = "metadata_snapshot"
    try:
        snapshot = refresh_metadata_catalog_snapshot(
            tenant_id=str(pool.tenant_id),
            database=database,
            requested_by_username=requested_by_username,
        )
        resolution = describe_metadata_catalog_snapshot_resolution(
            tenant_id=str(pool.tenant_id),
            database=database,
            snapshot=snapshot,
        )
        snapshot_payload = dict(snapshot.payload) if isinstance(snapshot.payload, dict) else {}
        metadata_snapshot = {
            "snapshot_id": str(snapshot.id),
            "source": str(snapshot.source or ""),
            "fetched_at": snapshot.fetched_at.isoformat() if snapshot.fetched_at else None,
            "catalog_version": str(snapshot.catalog_version or ""),
            "resolution_mode": resolution.resolution_mode,
            "is_shared_snapshot": bool(resolution.is_shared_snapshot),
            "provenance_database_id": resolution.provenance_database_id,
        }
        boundary_payload, boundary_payload_source = _resolve_boundary_validation_payload(
            database=database,
            snapshot=snapshot,
            requested_by_username=requested_by_username,
        )
        metadata_snapshot["validation_payload_source"] = boundary_payload_source
        checks.append(_check(key="published_metadata_refresh", ok=True, detail="metadata snapshot refreshed"))
    except Exception as exc:
        checks.append(_check(key="published_metadata_refresh", ok=False, detail=str(exc)))
        checks.append(_skipped_check("published_boundary", "published metadata refresh did not succeed"))
        checks.append(_skipped_check("gl_account_bindings", "published metadata refresh did not succeed"))
        checks.append(_skipped_check("bounded_scope", "published boundary validation did not succeed"))
        checks.append(_skipped_check("live_probe", "published metadata refresh did not succeed"))
        return _database_report(
            database=database,
            decision="no_go",
            scope_contract=scope_contract,
            checks=checks,
            source_state=source_state,
            metadata_snapshot=metadata_snapshot,
            live_probe=live_probe,
        )

    boundary_ok = False
    try:
        boundary = build_factual_odata_read_boundary(payload=boundary_payload or snapshot_payload or {})
        boundary_ok = True
        checks.append(
            _check(
                key="published_boundary",
                ok=True,
                detail="required factual published surfaces are available",
                metadata_payload_source=boundary_payload_source,
                boundary_kind=boundary.boundary_kind,
                direct_db_access=boundary.direct_db_access,
                entity_allowlist=list(boundary.entity_allowlist),
                function_allowlist=list(boundary.function_allowlist),
            )
        )
    except Exception as exc:
        checks.append(_check(key="published_boundary", ok=False, detail=str(exc)))

    if not boundary_ok:
        checks.append(_skipped_check("gl_account_bindings", "published boundary validation did not succeed"))
        checks.append(_skipped_check("bounded_scope", "published boundary validation did not succeed"))
        checks.append(_skipped_check("live_probe", "published boundary validation did not succeed"))
        return _database_report(
            database=database,
            decision="no_go",
            scope_contract=scope_contract,
            checks=checks,
            source_state=source_state,
            metadata_snapshot=metadata_snapshot,
            live_probe=live_probe,
        )

    try:
        scope_contract = resolve_pool_factual_sync_scope_for_database(
            pool=pool,
            database=database,
            quarter_start=quarter_start,
            quarter_end=quarter_end,
            organization_ids=organization_ids,
            movement_kinds=DEFAULT_FACTUAL_MOVEMENT_KINDS,
            verify_live_bindings=True,
        )
        checks.append(
            _check(
                key="gl_account_bindings",
                ok=True,
                detail="selected GLAccountSet coverage resolved and pinned for the target database",
                resolved_bindings=list(scope_contract.resolved_bindings),
            )
        )
    except FactualScopeSelectionError as exc:
        scope_contract = exc.scope
        checks.append(
            _check(
                key="gl_account_bindings",
                ok=False,
                detail=exc.detail,
                code=exc.code,
                blockers=list(exc.blockers),
            )
        )
        checks.append(
            _check(
                key="bounded_scope",
                ok=False,
                detail="scope contract could not be materialized from selected GLAccountSet bindings",
                scope=scope_contract.as_metadata(),
            )
        )
        checks.append(_skipped_check("live_probe", "GLAccountSet binding coverage did not succeed"))
        return _database_report(
            database=database,
            decision="no_go",
            scope_contract=scope_contract,
            checks=checks,
            source_state=source_state,
            metadata_snapshot=metadata_snapshot,
            live_probe=live_probe,
        )

    checks.append(
        _check(
            key="bounded_scope",
            ok=True,
            detail="scope is bounded by quarter, organizations, pinned GLAccountSet members, and movement kinds",
            scope=scope_contract.as_metadata(),
        )
    )

    try:
        live_probe = _run_live_probe(database=database, scope_contract=scope_contract)
        checks.append(
            _check(
                key="live_probe",
                ok=True,
                detail="live bounded factual reads completed successfully",
                boundary_reads=dict(live_probe["boundary_reads"]),
            )
        )
        decision = "go"
    except FactualPreflightError as exc:
        checks.append(_check(key="live_probe", ok=False, detail=exc.detail, code=exc.code))
        decision = "no_go"

    return _database_report(
        database=database,
        decision=decision,
        scope_contract=scope_contract,
        checks=checks,
        source_state=source_state,
        metadata_snapshot=metadata_snapshot,
        live_probe=live_probe,
    )


def _resolve_boundary_validation_payload(
    *,
    database: Database,
    snapshot,
    requested_by_username: str,
) -> tuple[dict[str, Any], str]:
    snapshot_payload = dict(snapshot.payload) if isinstance(snapshot.payload, dict) else {}
    database.refresh_from_db(fields=["metadata"])
    profile = get_business_configuration_profile(database=database) or {}
    observed_metadata_hash = str(profile.get("observed_metadata_hash") or "").strip()
    canonical_metadata_hash = str(
        profile.get("canonical_metadata_hash") or getattr(snapshot, "metadata_hash", "") or ""
    ).strip()

    if observed_metadata_hash and canonical_metadata_hash and observed_metadata_hash != canonical_metadata_hash:
        live_payload = _fetch_live_catalog_payload(
            database=database,
            requested_by_username=requested_by_username,
        )
        return (
            dict(live_payload) if isinstance(live_payload, dict) else {},
            "live_publication",
        )

    return snapshot_payload, "metadata_snapshot"


def _database_report(
    *,
    database: Database,
    decision: str,
    scope_contract,
    checks: list[dict[str, Any]],
    source_state,
    metadata_snapshot: dict[str, Any],
    live_probe: dict[str, Any],
) -> dict[str, Any]:
    return {
        "database_id": str(database.id),
        "database_name": str(database.name or ""),
        "decision": decision,
        "source_state": source_state.as_metadata(),
        "scope": scope_contract.as_metadata() if scope_contract is not None else {},
        "metadata_snapshot": metadata_snapshot,
        "live_probe": live_probe,
        "checks": checks,
    }


def _run_live_probe(*, database: Database, scope_contract) -> dict[str, Any]:
    odata_url = str(database.odata_url or "").strip()
    username = str(database.username or "").strip()
    password = str(database.password or "").strip()
    if not odata_url or not username or not password:
        raise FactualPreflightError(
            code="POOL_FACTUAL_PREFLIGHT_CREDENTIALS_INVALID",
            detail="Database OData URL and service credentials must be configured for factual live probe.",
        )

    account_code_refs = {
        str(binding.get("code") or "").strip(): str(binding.get("target_ref_key") or "").strip()
        for binding in getattr(scope_contract, "resolved_bindings", ())
        if str(binding.get("code") or "").strip() and str(binding.get("target_ref_key") or "").strip()
    }
    if not account_code_refs:
        account_code_refs = _resolve_account_code_refs(
            database=database,
            accounting_register_entity=scope_contract.accounting_register_entity,
            account_codes=scope_contract.account_codes,
        )
    accounting_entity = _build_accounting_register_entity(
        scope_contract=scope_contract,
        account_code_refs=account_code_refs,
    )
    accounting_rows = _query_all_rows(
        database=database,
        entity=accounting_entity,
        filter_query=None,
        order_by=None,
    )
    information_rows = _probe_entity_rows(
        database=database,
        entity=scope_contract.information_register_entity,
    )
    boundary_reads: dict[str, int] = {
        "accounting_register": len(accounting_rows),
        "information_register": len(information_rows),
    }
    boundary_probes: dict[str, dict[str, Any]] = {
        "accounting_register": {
            "entity": accounting_entity,
            "row_count": len(accounting_rows),
            "probe_ok": True,
        },
        "information_register": {
            "entity": scope_contract.information_register_entity,
            "row_count": len(information_rows),
            "probe_ok": True,
        },
    }
    document_refs_by_entity = _collect_accounting_document_refs(
        accounting_rows=accounting_rows,
        allowed_entities=scope_contract.document_entities,
    )
    for entity in scope_contract.document_entities:
        document_refs = document_refs_by_entity.get(str(entity), ())
        if document_refs:
            rows = _query_entity_refs(database=database, entity_refs=document_refs)
        else:
            rows = _probe_entity_rows(
                database=database,
                entity=entity,
            )
        boundary_reads[str(entity)] = len(rows)
        boundary_probes[str(entity)] = {
            "entity": str(entity),
            "row_count": len(rows),
            "probe_ok": True,
        }

    return {
        "read_boundary_kind": "odata",
        "accounting_register_entity": accounting_entity,
        "account_code_refs": account_code_refs,
        "resolved_bindings": list(getattr(scope_contract, "resolved_bindings", ())),
        "information_register_entity": REQUIRED_FACTUAL_INFORMATION_REGISTER,
        "boundary_reads": boundary_reads,
        "boundary_probes": boundary_probes,
    }


def _query_all_rows(
    *,
    database: Database,
    entity: str,
    filter_query: str | None,
    order_by: str | None,
) -> list[dict[str, Any]]:
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
                    entity_name=entity,
                    filter_query=filter_query,
                    order_by=order_by,
                    top=DEFAULT_FACTUAL_PREFLIGHT_PAGE_SIZE,
                    skip=skip,
                )
            except ODataQueryTransportError as exc:
                raise FactualPreflightError(
                    code="POOL_FACTUAL_PREFLIGHT_ODATA_TRANSPORT_FAILED",
                    detail=f"{entity}: {exc}",
                ) from exc

            if response.status_code >= 400:
                raise FactualPreflightError(
                    code="POOL_FACTUAL_PREFLIGHT_ODATA_QUERY_FAILED",
                    detail=f"{entity}: HTTP {response.status_code}: {_extract_response_detail(response)}",
                )
            try:
                payload = response.json()
            except ValueError as exc:
                raise FactualPreflightError(
                    code="POOL_FACTUAL_PREFLIGHT_ODATA_PAYLOAD_INVALID",
                    detail=f"{entity}: response is not valid JSON",
                ) from exc
            page_rows = payload.get("value", [])
            if not isinstance(page_rows, list):
                raise FactualPreflightError(
                    code="POOL_FACTUAL_PREFLIGHT_ODATA_PAYLOAD_INVALID",
                    detail=f"{entity}: response payload must contain JSON array 'value'",
                )
            rows.extend(item for item in page_rows if isinstance(item, dict))
            if len(page_rows) < DEFAULT_FACTUAL_PREFLIGHT_PAGE_SIZE:
                break
            skip += len(page_rows)
    return rows


def _probe_entity_rows(*, database: Database, entity: str) -> list[dict[str, Any]]:
    with ODataQueryAdapter(
        base_url=str(database.odata_url or ""),
        username=str(database.username or ""),
        password=str(database.password or ""),
        timeout=database.connection_timeout,
        verify_tls=resolve_database_odata_verify_tls(database=database),
    ) as adapter:
        try:
            response = adapter.query(
                entity_name=entity,
                top=1,
            )
        except ODataQueryTransportError as exc:
            raise FactualPreflightError(
                code="POOL_FACTUAL_PREFLIGHT_ODATA_TRANSPORT_FAILED",
                detail=f"{entity}: {exc}",
            ) from exc
        if response.status_code >= 400:
            raise FactualPreflightError(
                code="POOL_FACTUAL_PREFLIGHT_ODATA_QUERY_FAILED",
                detail=f"{entity}: HTTP {response.status_code}: {_extract_response_detail(response)}",
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise FactualPreflightError(
                code="POOL_FACTUAL_PREFLIGHT_ODATA_PAYLOAD_INVALID",
                detail=f"{entity}: response is not valid JSON",
            ) from exc
        page_rows = payload.get("value", [])
        if not isinstance(page_rows, list):
            raise FactualPreflightError(
                code="POOL_FACTUAL_PREFLIGHT_ODATA_PAYLOAD_INVALID",
                detail=f"{entity}: response payload must contain JSON array 'value'",
            )
        return [item for item in page_rows if isinstance(item, dict)]


def _build_accounting_register_entity(*, scope_contract, account_code_refs: dict[str, str]) -> str:
    start = f"{scope_contract.quarter_start.isoformat()}T00:00:00"
    end = f"{scope_contract.quarter_end.isoformat()}T23:59:59"
    condition = _build_accounting_register_condition(scope_contract=scope_contract)
    account_condition = _build_guid_or_filter(
        field="Account_Key",
        values=tuple(account_code_refs[code] for code in scope_contract.account_codes if code in account_code_refs),
    )
    period_arguments = _build_accounting_function_period_arguments(
        function_name=scope_contract.accounting_register_function,
        start=start,
        end=end,
    )
    return (
        f"{scope_contract.accounting_register_entity}/{scope_contract.accounting_register_function}("
        f"{period_arguments},"
        f"Condition='{_escape_odata_function_string(condition)}',"
        f"AccountCondition='{_escape_odata_function_string(account_condition)}'"
        ")"
    )


def _build_accounting_function_period_arguments(*, function_name: str, start: str, end: str) -> str:
    normalized = str(function_name or "").strip()
    if normalized == "Balance":
        return f"Period=datetime'{end}'"
    return f"StartPeriod=datetime'{start}',EndPeriod=datetime'{end}'"


def _build_temporal_entity_filter(
    *,
    field: str,
    organization_field: str,
    organization_ids: tuple[str, ...],
    quarter_start: date,
    quarter_end: date,
) -> str:
    parts = [
        (
            f"{field} ge datetime'{quarter_start.isoformat()}T00:00:00' and "
            f"{field} le datetime'{quarter_end.isoformat()}T23:59:59'"
        )
    ]
    organization_filter = _build_guid_or_filter(field=organization_field, values=organization_ids)
    if organization_filter:
        parts.append(f"({organization_filter})")
    return " and ".join(parts)


def _query_entity_refs(*, database: Database, entity_refs: Iterable[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with ODataQueryAdapter(
        base_url=str(database.odata_url or ""),
        username=str(database.username or ""),
        password=str(database.password or ""),
        timeout=database.connection_timeout,
        verify_tls=resolve_database_odata_verify_tls(database=database),
    ) as adapter:
        for entity_ref in entity_refs:
            try:
                response = adapter.query(entity_name=str(entity_ref), top=None)
            except ODataQueryTransportError as exc:
                raise FactualPreflightError(
                    code="POOL_FACTUAL_PREFLIGHT_ODATA_TRANSPORT_FAILED",
                    detail=f"{entity_ref}: {exc}",
                ) from exc
            if response.status_code >= 400:
                raise FactualPreflightError(
                    code="POOL_FACTUAL_PREFLIGHT_ODATA_QUERY_FAILED",
                    detail=f"{entity_ref}: HTTP {response.status_code}: {_extract_response_detail(response)}",
                )
            try:
                payload = response.json()
            except ValueError as exc:
                raise FactualPreflightError(
                    code="POOL_FACTUAL_PREFLIGHT_ODATA_PAYLOAD_INVALID",
                    detail=f"{entity_ref}: response is not valid JSON",
                ) from exc
            if isinstance(payload, dict) and isinstance(payload.get("value"), list):
                rows.extend(item for item in payload["value"] if isinstance(item, dict))
                continue
            if isinstance(payload, dict):
                rows.append(payload)
                continue
            raise FactualPreflightError(
                code="POOL_FACTUAL_PREFLIGHT_ODATA_PAYLOAD_INVALID",
                detail=f"{entity_ref}: response payload must contain JSON object or array 'value'",
            )
    return rows


def _collect_accounting_document_refs(
    *,
    accounting_rows: Iterable[dict[str, Any]],
    allowed_entities: Iterable[str],
) -> dict[str, tuple[str, ...]]:
    allowed = {str(entity or "").strip() for entity in allowed_entities if str(entity or "").strip()}
    collected: dict[str, list[str]] = {}
    seen: dict[str, set[str]] = {}
    for row in accounting_rows:
        document_ref = _extract_document_ref_from_accounting_row(row)
        entity_name = _extract_document_entity_name(document_ref)
        if not entity_name or entity_name not in allowed:
            continue
        entity_seen = seen.setdefault(entity_name, set())
        if document_ref in entity_seen:
            continue
        entity_seen.add(document_ref)
        collected.setdefault(entity_name, []).append(document_ref)
    return {entity: tuple(refs) for entity, refs in collected.items()}


def _extract_document_ref_from_accounting_row(row: dict[str, Any]) -> str:
    dimension_pairs = (
        ("ExtDimension1", "ExtDimension1_Type"),
        ("ExtDimension2", "ExtDimension2_Type"),
        ("ExtDimension3", "ExtDimension3_Type"),
        ("BalancedExtDimension1", "BalancedExtDimension1_Type"),
        ("BalancedExtDimension2", "BalancedExtDimension2_Type"),
        ("BalancedExtDimension3", "BalancedExtDimension3_Type"),
    )
    for value_field, type_field in dimension_pairs:
        entity_type = _normalize_accounting_document_entity_type(row.get(type_field))
        raw_value = str(row.get(value_field) or "").strip()
        if not entity_type or not raw_value:
            continue
        if "(guid'" in raw_value.lower():
            return raw_value
        return f"{entity_type}(guid'{raw_value}')"
    for field_name in ("Документ", "Document", "source_document_ref", "document_ref"):
        raw_value = str(row.get(field_name) or "").strip()
        if _extract_document_entity_name(raw_value):
            return raw_value
    return ""


def _normalize_accounting_document_entity_type(raw_value: Any) -> str:
    entity_type = str(raw_value or "").strip()
    if entity_type.startswith("StandardODATA."):
        entity_type = entity_type.removeprefix("StandardODATA.")
    if entity_type.startswith("standardodata."):
        entity_type = entity_type.removeprefix("standardodata.")
    if not entity_type.startswith("Document_"):
        return ""
    return entity_type


def _extract_document_entity_name(document_ref: str) -> str:
    raw_value = str(document_ref or "").strip()
    open_paren = raw_value.find("(")
    if open_paren <= 0:
        return ""
    entity_name = raw_value[:open_paren].strip()
    if not entity_name.startswith("Document_"):
        return ""
    return entity_name


def _build_accounting_register_condition(*, scope_contract) -> str:
    parts: list[str] = []
    organization_filter = _build_guid_or_filter(
        field="Организация_Key",
        values=scope_contract.organization_ids,
    )
    if organization_filter:
        parts.append(f"({organization_filter})")
    return " and ".join(parts)


def _resolve_account_code_refs(
    *,
    database: Database,
    accounting_register_entity: str,
    account_codes: Iterable[str],
) -> dict[str, str]:
    chart_entity = _derive_chart_of_accounts_entity(accounting_register_entity)
    rows = _query_all_rows(
        database=database,
        entity=chart_entity,
        filter_query=None,
        order_by=None,
    )
    required_codes = tuple(str(code or "").strip() for code in account_codes if str(code or "").strip())
    resolved: dict[str, str] = {}
    for row in rows:
        code = str(row.get("Code") or row.get("code") or "").strip()
        ref_key = str(row.get("Ref_Key") or row.get("ref_key") or "").strip()
        if not code or not ref_key or code not in required_codes:
            continue
        resolved[code] = ref_key
        if len(resolved) == len(required_codes):
            break

    missing_codes = sorted(code for code in required_codes if code not in resolved)
    if missing_codes:
        raise FactualPreflightError(
            code="POOL_FACTUAL_PREFLIGHT_ACCOUNT_CODES_UNRESOLVED",
            detail=(
                f"{chart_entity}: missing account codes required for factual scope: "
                + ", ".join(missing_codes)
            ),
        )
    return resolved


def _derive_chart_of_accounts_entity(accounting_register_entity: str) -> str:
    normalized = str(accounting_register_entity or "").strip()
    if normalized.startswith("AccountingRegister_"):
        return normalized.replace("AccountingRegister_", "ChartOfAccounts_", 1)
    return "ChartOfAccounts_Хозрасчетный"


def _build_guid_or_filter(*, field: str, values: Iterable[str]) -> str:
    clauses = [f"{field} eq guid'{value}'" for value in values if str(value).strip()]
    return " or ".join(clauses)


def _escape_odata_literal(value: str) -> str:
    return value.replace("'", "''")


def _escape_odata_function_string(value: str) -> str:
    return value.replace("'", "''")


def _extract_response_detail(response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return str(response.text or "").strip()[:500]
    if isinstance(payload, dict):
        if isinstance(payload.get("odata.error"), dict):
            message = payload["odata.error"].get("message")
            if isinstance(message, dict):
                return str(message.get("value") or "").strip() or json.dumps(payload, ensure_ascii=False)
            return str(message or "").strip() or json.dumps(payload, ensure_ascii=False)
        return json.dumps(payload, ensure_ascii=False)[:500]
    return str(payload)[:500]


def _check(*, key: str, ok: bool, detail: str, **extra: Any) -> dict[str, Any]:
    return {
        "key": key,
        "ok": bool(ok),
        "status": "pass" if ok else "fail",
        "detail": str(detail or ""),
        **extra,
    }


def _skipped_check(key: str, detail: str) -> dict[str, Any]:
    return {
        "key": key,
        "ok": False,
        "status": "skip",
        "detail": detail,
    }


__all__ = ["run_pool_factual_sync_preflight"]
