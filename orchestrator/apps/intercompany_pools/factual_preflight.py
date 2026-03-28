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

from .factual_read_boundary import build_factual_odata_read_boundary
from .factual_source_profile import REQUIRED_FACTUAL_INFORMATION_REGISTER
from .factual_sync_runtime import (
    build_factual_sales_report_sync_scope,
    resolve_factual_sync_source_state,
)
from .factual_workspace_runtime import (
    DEFAULT_FACTUAL_ACCOUNT_CODES,
    DEFAULT_FACTUAL_MOVEMENT_KINDS,
    resolve_pool_factual_scope,
)
from .metadata_catalog import (
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

    scope_contract = build_factual_sales_report_sync_scope(
        quarter_start=quarter_start,
        quarter_end=scope.quarter_end,
        organization_ids=scope.organization_ids,
        account_codes=DEFAULT_FACTUAL_ACCOUNT_CODES,
        movement_kinds=DEFAULT_FACTUAL_MOVEMENT_KINDS,
    )

    database_reports = [
        _run_database_preflight(
            pool=pool,
            database=database,
            scope_contract=scope_contract,
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
    scope_contract,
    requested_by_username: str,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    source_state = resolve_factual_sync_source_state(database=database)
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
        checks.append(_check(key="published_metadata_refresh", ok=True, detail="metadata snapshot refreshed"))
    except Exception as exc:
        checks.append(_check(key="published_metadata_refresh", ok=False, detail=str(exc)))
        checks.append(_skipped_check("published_boundary", "published metadata refresh did not succeed"))
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
        boundary = build_factual_odata_read_boundary(payload=snapshot_payload or {})
        boundary_ok = True
        checks.append(
            _check(
                key="published_boundary",
                ok=True,
                detail="required factual published surfaces are available",
                boundary_kind=boundary.boundary_kind,
                direct_db_access=boundary.direct_db_access,
                entity_allowlist=list(boundary.entity_allowlist),
                function_allowlist=list(boundary.function_allowlist),
            )
        )
    except Exception as exc:
        checks.append(_check(key="published_boundary", ok=False, detail=str(exc)))

    if not boundary_ok:
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

    checks.append(
        _check(
            key="bounded_scope",
            ok=True,
            detail="scope is bounded by quarter, organizations, account codes, and movement kinds",
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
        "scope": scope_contract.as_metadata(),
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

    accounting_entity = _build_accounting_register_entity(scope_contract=scope_contract)
    accounting_rows = _query_all_rows(
        database=database,
        entity=accounting_entity,
        filter_query=None,
        order_by=None,
    )
    information_rows = _query_all_rows(
        database=database,
        entity=scope_contract.information_register_entity,
        filter_query=_build_temporal_entity_filter(
            field="Period",
            organization_ids=scope_contract.organization_ids,
            quarter_start=scope_contract.quarter_start,
            quarter_end=scope_contract.quarter_end,
        ),
        order_by="Period desc",
    )
    boundary_reads: dict[str, int] = {
        "accounting_register": len(accounting_rows),
        "information_register": len(information_rows),
    }
    for entity in scope_contract.document_entities:
        rows = _query_all_rows(
            database=database,
            entity=entity,
            filter_query=_build_temporal_entity_filter(
                field="Date",
                organization_ids=scope_contract.organization_ids,
                quarter_start=scope_contract.quarter_start,
                quarter_end=scope_contract.quarter_end,
            ),
            order_by="Date desc",
        )
        boundary_reads[str(entity)] = len(rows)

    return {
        "read_boundary_kind": "odata",
        "accounting_register_entity": accounting_entity,
        "information_register_entity": REQUIRED_FACTUAL_INFORMATION_REGISTER,
        "boundary_reads": boundary_reads,
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


def _build_accounting_register_entity(*, scope_contract) -> str:
    start = f"{scope_contract.quarter_start.isoformat()}T00:00:00"
    end = f"{scope_contract.quarter_end.isoformat()}T23:59:59"
    condition = _build_accounting_register_condition(scope_contract=scope_contract)
    account_condition = _build_code_filter(field="Code", values=scope_contract.account_codes)
    return (
        f"{scope_contract.accounting_register_entity}/{scope_contract.accounting_register_function}("
        f"PeriodStart=datetime'{start}',"
        f"PeriodEnd=datetime'{end}',"
        f"Condition='{_escape_odata_function_string(condition)}',"
        f"AccountCondition='{_escape_odata_function_string(account_condition)}'"
        ")"
    )


def _build_temporal_entity_filter(
    *,
    field: str,
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
    organization_filter = _build_guid_or_filter(field="Organization_Key", values=organization_ids)
    if organization_filter:
        parts.append(f"({organization_filter})")
    return " and ".join(parts)


def _build_accounting_register_condition(*, scope_contract) -> str:
    parts: list[str] = []
    organization_filter = _build_guid_or_filter(
        field="Organization_Key",
        values=scope_contract.organization_ids,
    )
    if organization_filter:
        parts.append(f"({organization_filter})")
    record_type_filter = _build_record_type_filter(scope_contract.movement_kinds)
    if record_type_filter:
        parts.append(record_type_filter)
    return " and ".join(parts)


def _build_record_type_filter(movement_kinds: Iterable[str]) -> str:
    clauses: list[str] = []
    for kind in movement_kinds:
        normalized = str(kind or "").strip().lower()
        if normalized == "credit":
            clauses.append("RecordType eq 'Credit'")
        elif normalized == "debit":
            clauses.append("RecordType eq 'Debit'")
    if not clauses:
        return ""
    if len(clauses) == 1:
        return clauses[0]
    return f"({' or '.join(clauses)})"


def _build_guid_or_filter(*, field: str, values: Iterable[str]) -> str:
    clauses = [f"{field} eq guid'{value}'" for value in values if str(value).strip()]
    return " or ".join(clauses)


def _build_code_filter(*, field: str, values: Iterable[str]) -> str:
    clauses = [f"{field} eq '{_escape_odata_literal(str(value))}'" for value in values if str(value).strip()]
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
