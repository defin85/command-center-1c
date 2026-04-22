from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone

from apps.databases.models import Database
from apps.tenancy.models import Tenant

from .business_configuration_profile import get_business_configuration_profile
from .master_data_bindings import upsert_pool_master_data_binding
from .master_data_bootstrap_import_source_adapter import (
    fetch_pool_master_data_bootstrap_source_rows,
    run_pool_master_data_bootstrap_source_preflight,
)
from .master_data_canonical_upsert import MasterDataCanonicalUpsertError, upsert_pool_master_data_gl_account
from .master_data_sync_redaction import sanitize_master_data_sync_text, sanitize_master_data_sync_value
from .models import (
    PoolMasterBindingSyncStatus,
    PoolMasterDataBinding,
    PoolMasterDataChartFollowerStatus,
    PoolMasterDataChartFollowerVerdict,
    PoolMasterDataChartMaterializationJob,
    PoolMasterDataChartMaterializationJobStatus,
    PoolMasterDataChartMaterializationMode,
    PoolMasterDataChartSnapshot,
    PoolMasterDataChartSource,
    PoolMasterDataChartSourceStatus,
    PoolMasterGLAccount,
)


CHART_SOURCE_NOT_FOUND = "CHART_SOURCE_NOT_FOUND"
CHART_SOURCE_DATABASE_NOT_FOUND = "CHART_SOURCE_DATABASE_NOT_FOUND"
CHART_SOURCE_DATABASE_TENANT_MISMATCH = "CHART_SOURCE_DATABASE_TENANT_MISMATCH"
CHART_SOURCE_BUSINESS_PROFILE_MISSING = "CHART_SOURCE_BUSINESS_PROFILE_MISSING"
CHART_SOURCE_BUSINESS_PROFILE_MISMATCH = "CHART_SOURCE_BUSINESS_PROFILE_MISMATCH"
CHART_SOURCE_CHART_IDENTITY_REQUIRED = "CHART_SOURCE_CHART_IDENTITY_REQUIRED"
CHART_SOURCE_ROWS_EMPTY = "CHART_SOURCE_ROWS_EMPTY"
CHART_SOURCE_FETCH_FAILED = "CHART_SOURCE_FETCH_FAILED"
CHART_SOURCE_PREFLIGHT_FAILED = "CHART_SOURCE_PREFLIGHT_FAILED"
CHART_JOB_NOT_FOUND = "CHART_JOB_NOT_FOUND"
CHART_JOB_MODE_INVALID = "CHART_JOB_MODE_INVALID"

_CHART_PROVENANCE_KEY = "chart_materialization"
_TERMINAL_JOB_STATUSES = {
    PoolMasterDataChartMaterializationJobStatus.SUCCEEDED,
    PoolMasterDataChartMaterializationJobStatus.FAILED,
}


def list_pool_master_data_chart_sources(
    *,
    tenant_id: str,
    chart_identity: str = "",
    config_name: str = "",
    config_version: str = "",
    database_id: str = "",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PoolMasterDataChartSource], int]:
    queryset = PoolMasterDataChartSource.objects.select_related("database").filter(tenant_id=str(tenant_id or "").strip())
    if str(chart_identity or "").strip():
        queryset = queryset.filter(chart_identity=str(chart_identity).strip())
    if str(config_name or "").strip():
        queryset = queryset.filter(config_name=str(config_name).strip())
    if str(config_version or "").strip():
        queryset = queryset.filter(config_version=str(config_version).strip())
    if str(database_id or "").strip():
        queryset = queryset.filter(database_id=str(database_id).strip())
    total = queryset.count()
    rows = list(queryset.order_by("chart_identity", "config_name", "config_version")[max(0, offset) : max(0, offset) + max(1, limit)])
    return rows, total


def upsert_pool_master_data_chart_source(
    *,
    tenant: Tenant,
    database: Database,
    chart_identity: str,
    existing_source: PoolMasterDataChartSource | None = None,
) -> tuple[PoolMasterDataChartSource, bool]:
    if str(database.tenant_id) != str(tenant.id):
        raise ValueError(
            f"{CHART_SOURCE_DATABASE_TENANT_MISMATCH}: database '{database.id}' does not belong to tenant '{tenant.id}'"
        )
    normalized_chart_identity = str(chart_identity or "").strip()
    if not normalized_chart_identity:
        raise ValueError(f"{CHART_SOURCE_CHART_IDENTITY_REQUIRED}: chart_identity is required")
    profile = _require_business_profile(database=database)
    payload = {
        "tenant": tenant,
        "database": database,
        "chart_identity": normalized_chart_identity,
        "config_name": str(profile["config_name"]),
        "config_version": str(profile["config_version"]),
        "status": PoolMasterDataChartSourceStatus.ACTIVE,
        "last_error_code": "",
        "last_error": "",
        "metadata": _merge_source_metadata(
            existing_source.metadata if existing_source is not None else {},
            {
                "business_configuration_profile": {
                    "config_name": str(profile["config_name"]),
                    "config_version": str(profile["config_version"]),
                    "verification_status": str(profile.get("verification_status") or ""),
                    "verified_at": str(profile.get("verified_at") or ""),
                }
            },
        ),
    }

    with transaction.atomic():
        source = existing_source
        if source is None:
            source = PoolMasterDataChartSource.objects.filter(
                tenant=tenant,
                chart_identity=normalized_chart_identity,
                config_name=str(profile["config_name"]),
                config_version=str(profile["config_version"]),
            ).first()
        created = source is None
        if created:
            source = PoolMasterDataChartSource.objects.create(**payload)
            return source, True

        changed_fields: list[str] = []
        for field_name, new_value in payload.items():
            if getattr(source, field_name) != new_value:
                setattr(source, field_name, new_value)
                changed_fields.append(field_name)
        if changed_fields:
            source.save(update_fields=[*changed_fields, "updated_at"])
        return source, False


def list_pool_master_data_chart_jobs(
    *,
    tenant_id: str,
    chart_source_id: str = "",
    mode: str = "",
    status: str = "",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PoolMasterDataChartMaterializationJob], int]:
    queryset = (
        PoolMasterDataChartMaterializationJob.objects.select_related("chart_source", "chart_source__database", "snapshot")
        .prefetch_related("follower_statuses__database")
        .filter(tenant_id=str(tenant_id or "").strip())
    )
    if str(chart_source_id or "").strip():
        queryset = queryset.filter(chart_source_id=str(chart_source_id).strip())
    if str(mode or "").strip():
        queryset = queryset.filter(mode=str(mode).strip())
    if str(status or "").strip():
        queryset = queryset.filter(status=str(status).strip())
    total = queryset.count()
    rows = list(queryset.order_by("-created_at")[max(0, offset) : max(0, offset) + max(1, limit)])
    return rows, total


def get_pool_master_data_chart_job(*, tenant_id: str, job_id: str) -> PoolMasterDataChartMaterializationJob:
    job = (
        PoolMasterDataChartMaterializationJob.objects.select_related("chart_source", "chart_source__database", "snapshot")
        .prefetch_related("follower_statuses__database")
        .filter(id=str(job_id or "").strip(), tenant_id=str(tenant_id or "").strip())
        .first()
    )
    if job is None:
        raise ValueError(f"{CHART_JOB_NOT_FOUND}: chart materialization job not found")
    return job


def create_pool_master_data_chart_job(
    *,
    tenant: Tenant,
    chart_source: PoolMasterDataChartSource,
    mode: str,
    database_ids: Iterable[str] | None = None,
    requested_by_username: str = "",
) -> PoolMasterDataChartMaterializationJob:
    normalized_mode = _normalize_job_mode(mode)
    if str(chart_source.tenant_id) != str(tenant.id):
        raise ValueError(
            f"{CHART_SOURCE_DATABASE_TENANT_MISMATCH}: chart source '{chart_source.id}' does not belong to tenant '{tenant.id}'"
        )
    normalized_database_ids = [
        str(item).strip()
        for item in (database_ids or [])
        if str(item).strip()
    ]
    job = PoolMasterDataChartMaterializationJob.objects.create(
        tenant=tenant,
        chart_source=chart_source,
        mode=normalized_mode,
        status=PoolMasterDataChartMaterializationJobStatus.PENDING,
        database_ids=normalized_database_ids,
        requested_by_username=str(requested_by_username or "").strip(),
    )
    _append_job_audit(
        job=job,
        action="job_created",
        metadata={
            "mode": normalized_mode,
            "chart_source_id": str(chart_source.id),
            "database_ids": normalized_database_ids,
        },
    )
    return _execute_chart_job(job=job)


def serialize_pool_master_data_chart_source(source: PoolMasterDataChartSource) -> dict[str, Any]:
    latest_snapshot = (
        source.snapshots.order_by("-created_at").first()
        if hasattr(source, "snapshots")
        else None
    )
    latest_job = source.jobs.order_by("-created_at").first() if hasattr(source, "jobs") else None
    return {
        "id": str(source.id),
        "tenant_id": str(source.tenant_id),
        "database_id": str(source.database_id),
        "database_name": str(source.database.name or ""),
        "cluster_id": str(source.database.cluster_id) if getattr(source.database, "cluster_id", None) else None,
        "chart_identity": str(source.chart_identity or ""),
        "config_name": str(source.config_name or ""),
        "config_version": str(source.config_version or ""),
        "status": str(source.status or ""),
        "last_success_at": source.last_success_at,
        "last_error_code": str(source.last_error_code or ""),
        "last_error": str(source.last_error or ""),
        "metadata": sanitize_master_data_sync_value(dict(source.metadata or {})),
        "latest_snapshot": serialize_pool_master_data_chart_snapshot(latest_snapshot) if latest_snapshot else None,
        "latest_job": serialize_pool_master_data_chart_job(
            latest_job,
            include_follower_statuses=False,
            include_chart_source=False,
        ) if latest_job else None,
        "candidate_databases": _serialize_candidate_databases(source=source),
        "created_at": source.created_at,
        "updated_at": source.updated_at,
    }


def serialize_pool_master_data_chart_snapshot(snapshot: PoolMasterDataChartSnapshot | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    return {
        "id": str(snapshot.id),
        "tenant_id": str(snapshot.tenant_id),
        "chart_source_id": str(snapshot.chart_source_id),
        "fingerprint": str(snapshot.fingerprint or ""),
        "row_count": int(snapshot.row_count or 0),
        "materialized_count": int(snapshot.materialized_count or 0),
        "updated_count": int(snapshot.updated_count or 0),
        "unchanged_count": int(snapshot.unchanged_count or 0),
        "retired_count": int(snapshot.retired_count or 0),
        "metadata": sanitize_master_data_sync_value(dict(snapshot.metadata or {})),
        "created_at": snapshot.created_at,
    }


def serialize_pool_master_data_chart_follower_status(status_row: PoolMasterDataChartFollowerStatus) -> dict[str, Any]:
    diagnostics = sanitize_master_data_sync_value(dict(status_row.diagnostics or {}))
    return {
        "id": str(status_row.id),
        "tenant_id": str(status_row.tenant_id),
        "job_id": str(status_row.job_id),
        "snapshot_id": str(status_row.snapshot_id) if status_row.snapshot_id else None,
        "database_id": str(status_row.database_id),
        "database_name": str(status_row.database.name or ""),
        "cluster_id": str(status_row.database.cluster_id) if getattr(status_row.database, "cluster_id", None) else None,
        "verdict": str(status_row.verdict or ""),
        "detail": str(status_row.detail or ""),
        "matched_accounts": int(status_row.matched_accounts or 0),
        "missing_accounts": int(status_row.missing_accounts or 0),
        "ambiguous_accounts": int(status_row.ambiguous_accounts or 0),
        "stale_bindings": int(status_row.stale_bindings or 0),
        "backfilled_accounts": int(status_row.backfilled_accounts or 0),
        "diagnostics": diagnostics,
        "bindings_remediation_href": _build_bindings_remediation_href(diagnostics=diagnostics),
        "last_verified_at": status_row.last_verified_at,
        "created_at": status_row.created_at,
        "updated_at": status_row.updated_at,
    }


def serialize_pool_master_data_chart_job(
    job: PoolMasterDataChartMaterializationJob,
    *,
    include_follower_statuses: bool = True,
    include_chart_source: bool = True,
) -> dict[str, Any]:
    follower_statuses = []
    if include_follower_statuses:
        follower_statuses = [
            serialize_pool_master_data_chart_follower_status(item)
            for item in job.follower_statuses.select_related("database").order_by("database__name", "id")
        ]
    return {
        "id": str(job.id),
        "tenant_id": str(job.tenant_id),
        "chart_source_id": str(job.chart_source_id),
        "chart_source": (
            serialize_pool_master_data_chart_source(job.chart_source)
            if include_chart_source and hasattr(job, "chart_source")
            else None
        ),
        "snapshot": serialize_pool_master_data_chart_snapshot(job.snapshot),
        "mode": str(job.mode or ""),
        "status": str(job.status or ""),
        "database_ids": [str(item) for item in (job.database_ids or [])],
        "requested_by_username": str(job.requested_by_username or ""),
        "last_error_code": str(job.last_error_code or ""),
        "last_error": str(job.last_error or ""),
        "counters": sanitize_master_data_sync_value(dict(job.counters or {})),
        "diagnostics": sanitize_master_data_sync_value(dict(job.diagnostics or {})),
        "audit_trail": sanitize_master_data_sync_value(list(job.audit_trail or [])),
        "follower_statuses": follower_statuses,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def _execute_chart_job(job: PoolMasterDataChartMaterializationJob) -> PoolMasterDataChartMaterializationJob:
    started_at = timezone.now()
    job.status = PoolMasterDataChartMaterializationJobStatus.RUNNING
    job.started_at = started_at
    job.finished_at = None
    job.last_error_code = ""
    job.last_error = ""
    job.diagnostics = {}
    job.counters = {}
    _append_job_audit(job=job, action="job_started", metadata={"started_at": started_at.isoformat()})
    job.save(
        update_fields=[
            "status",
            "started_at",
            "finished_at",
            "last_error_code",
            "last_error",
            "diagnostics",
            "counters",
            "audit_trail",
            "updated_at",
        ]
    )

    try:
        preflight = _run_chart_source_preflight(source=job.chart_source)
        if not bool(preflight.get("ok")):
            first_error = (preflight.get("errors") or [{}])[0] if isinstance(preflight.get("errors"), list) else {}
            job.counters = {
                "source_ok": False,
                "candidate_follower_count": int(preflight.get("candidate_follower_count") or 0),
            }
            job.diagnostics = preflight
            raise ValueError(
                f"{str(first_error.get('code') or CHART_SOURCE_PREFLIGHT_FAILED)}: "
                f"{str(first_error.get('detail') or 'Chart source preflight failed.')}"
            )
        if job.mode == PoolMasterDataChartMaterializationMode.PREFLIGHT:
            job.counters = sanitize_master_data_sync_value({
                "source_ok": bool(preflight.get("ok")),
                "candidate_follower_count": int(preflight.get("candidate_follower_count") or 0),
            })
            job.diagnostics = sanitize_master_data_sync_value(preflight)
        elif job.mode == PoolMasterDataChartMaterializationMode.DRY_RUN:
            rows = _load_source_gl_account_rows(source=job.chart_source)
            job.counters = sanitize_master_data_sync_value(_build_dry_run_summary(source=job.chart_source, rows=rows))
            job.diagnostics = sanitize_master_data_sync_value(preflight)
        elif job.mode == PoolMasterDataChartMaterializationMode.MATERIALIZE:
            rows = _load_source_gl_account_rows(source=job.chart_source)
            snapshot, counters = _materialize_chart_snapshot(source=job.chart_source, rows=rows)
            job.snapshot = snapshot
            job.counters = sanitize_master_data_sync_value(counters)
            job.diagnostics = sanitize_master_data_sync_value(preflight)
        elif job.mode in {
            PoolMasterDataChartMaterializationMode.VERIFY_FOLLOWERS,
            PoolMasterDataChartMaterializationMode.BACKFILL_BINDINGS,
        }:
            snapshot = _require_latest_snapshot(source=job.chart_source)
            job.snapshot = snapshot
            counters, diagnostics = _run_follower_resolution(
                job=job,
                source=job.chart_source,
                snapshot=snapshot,
                mode=job.mode,
                database_ids=job.database_ids or [],
            )
            job.counters = sanitize_master_data_sync_value(counters)
            job.diagnostics = sanitize_master_data_sync_value({
                "preflight": preflight,
                "resolution": diagnostics,
            })
        else:
            raise ValueError(f"{CHART_JOB_MODE_INVALID}: unsupported chart materialization mode '{job.mode}'")

        finished_at = timezone.now()
        job.status = PoolMasterDataChartMaterializationJobStatus.SUCCEEDED
        job.finished_at = finished_at
        _append_job_audit(job=job, action="job_succeeded", metadata={"finished_at": finished_at.isoformat()})
    except Exception as exc:
        code, detail, diagnostics = _resolve_chart_job_error(exc)
        finished_at = timezone.now()
        job.status = PoolMasterDataChartMaterializationJobStatus.FAILED
        job.finished_at = finished_at
        job.last_error_code = code
        job.last_error = detail
        job.diagnostics = sanitize_master_data_sync_value(
            _merge_source_metadata(
                dict(job.diagnostics or {}),
                diagnostics,
            )
        )
        _append_job_audit(
            job=job,
            action="job_failed",
            metadata={
                "finished_at": finished_at.isoformat(),
                "error_code": code,
                "detail": detail,
            },
        )

    job.save(
        update_fields=[
            "snapshot",
            "status",
            "last_error_code",
            "last_error",
            "counters",
            "diagnostics",
            "audit_trail",
            "finished_at",
            "updated_at",
        ]
    )
    return get_pool_master_data_chart_job(tenant_id=str(job.tenant_id), job_id=str(job.id))


def _run_chart_source_preflight(*, source: PoolMasterDataChartSource) -> dict[str, Any]:
    profile = _require_business_profile(database=source.database)
    if (
        str(profile["config_name"]).strip() != str(source.config_name).strip()
        or str(profile["config_version"]).strip() != str(source.config_version).strip()
    ):
        raise ValueError(
            f"{CHART_SOURCE_BUSINESS_PROFILE_MISMATCH}: authoritative source compatibility class no longer matches database business configuration profile"
        )
    preflight = run_pool_master_data_bootstrap_source_preflight(
        tenant_id=str(source.tenant_id),
        database=source.database,
        entity_scope=["gl_account"],
    )
    serialized = {
        "ok": bool(preflight.ok),
        "chart_source_id": str(source.id),
        "source_database_id": str(source.database_id),
        "chart_identity": str(source.chart_identity or ""),
        "config_name": str(source.config_name or ""),
        "config_version": str(source.config_version or ""),
        "candidate_follower_count": len(_resolve_compatible_databases(source=source)),
        "coverage": dict(preflight.coverage or {}),
        "credential_strategy": str(preflight.credential_strategy or ""),
        "errors": sanitize_master_data_sync_value(list(preflight.errors or [])),
        "diagnostics": sanitize_master_data_sync_value(
            _merge_source_metadata(
                dict(preflight.diagnostics or {}),
                {
                    "business_configuration_profile": profile,
                    "candidate_follower_database_ids": [
                        str(database.id) for database in _resolve_compatible_databases(source=source)
                    ],
                },
            )
        ),
    }
    if not serialized["ok"]:
        source.status = PoolMasterDataChartSourceStatus.ERROR
        source.last_error_code = str((serialized["errors"][0] or {}).get("code") or CHART_SOURCE_PREFLIGHT_FAILED) if serialized["errors"] else CHART_SOURCE_PREFLIGHT_FAILED
        source.last_error = str((serialized["errors"][0] or {}).get("detail") or "Chart source preflight failed.") if serialized["errors"] else "Chart source preflight failed."
        source.save(update_fields=["status", "last_error_code", "last_error", "updated_at"])
    return serialized


def _load_source_gl_account_rows(*, source: PoolMasterDataChartSource) -> list[dict[str, Any]]:
    try:
        rows = fetch_pool_master_data_bootstrap_source_rows(
            tenant_id=str(source.tenant_id),
            database=source.database,
            entity_type="gl_account",
        )
    except Exception as exc:
        raise ValueError(f"{CHART_SOURCE_FETCH_FAILED}: {exc}") from exc

    normalized_target_chart = _normalize_chart_identity(source.chart_identity)
    result: list[dict[str, Any]] = []
    for row in rows:
        row_chart_identity = str(row.get("chart_identity") or "").strip()
        if _normalize_chart_identity(row_chart_identity) != normalized_target_chart:
            continue
        code = str(row.get("code") or "").strip()
        name = str(row.get("name") or "").strip()
        if not code or not name:
            continue
        row_config_name = str(row.get("config_name") or source.config_name or "").strip()
        row_config_version = str(row.get("config_version") or source.config_version or "").strip()
        if row_config_name != str(source.config_name).strip() or row_config_version != str(source.config_version).strip():
            continue
        source_ref = _read_row_source_ref(row=row, fallback=code)
        result.append(
            {
                "source_canonical_id": str(row.get("canonical_id") or "").strip(),
                "source_ref": source_ref,
                "code": code,
                "name": name,
                "chart_identity": row_chart_identity,
                "config_name": row_config_name,
                "config_version": row_config_version,
                "metadata": sanitize_master_data_sync_value(dict(row.get("metadata") or {})),
            }
        )
    result.sort(key=lambda item: (_normalize_code(item["code"]), str(item["name"]).strip(), item["source_ref"]))
    if not result:
        raise ValueError(
            f"{CHART_SOURCE_ROWS_EMPTY}: no GLAccount rows matched chart_identity '{source.chart_identity}' and compatibility class '{source.config_name} / {source.config_version}'"
        )
    return result


def _build_dry_run_summary(
    *,
    source: PoolMasterDataChartSource,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    expected_ids = {_build_gl_account_canonical_id(chart_identity=item["chart_identity"], code=item["code"]) for item in rows}
    existing_accounts = {
        str(account.canonical_id): account
        for account in PoolMasterGLAccount.objects.filter(
            tenant_id=source.tenant_id,
            chart_identity=source.chart_identity,
            config_name=source.config_name,
            config_version=source.config_version,
        )
    }
    created_count = 0
    updated_count = 0
    unchanged_count = 0
    for row in rows:
        canonical_id = _build_gl_account_canonical_id(chart_identity=row["chart_identity"], code=row["code"])
        account = existing_accounts.get(canonical_id)
        if account is None:
            created_count += 1
            continue
        expected_metadata = _build_gl_account_metadata(
            existing_metadata=dict(account.metadata or {}),
            source=source,
            snapshot_fingerprint=_compute_chart_snapshot_fingerprint(rows=rows),
            row=row,
        )
        if (
            account.code != row["code"]
            or account.name != row["name"]
            or account.chart_identity != row["chart_identity"]
            or account.config_name != row["config_name"]
            or account.config_version != row["config_version"]
            or bool(account.is_retired)
            or dict(account.metadata or {}) != expected_metadata
        ):
            updated_count += 1
            continue
        unchanged_count += 1
    retired_count = PoolMasterGLAccount.objects.filter(
        tenant_id=source.tenant_id,
        chart_identity=source.chart_identity,
        config_name=source.config_name,
        config_version=source.config_version,
        is_retired=False,
    ).exclude(canonical_id__in=expected_ids).count()
    return {
        "rows_total": len(rows),
        "created_count": created_count,
        "updated_count": updated_count,
        "unchanged_count": unchanged_count,
        "retired_count": retired_count,
        "compatibility_class": {
            "chart_identity": str(source.chart_identity),
            "config_name": str(source.config_name),
            "config_version": str(source.config_version),
        },
        "candidate_follower_count": len(_resolve_compatible_databases(source=source)),
    }


def _materialize_chart_snapshot(
    *,
    source: PoolMasterDataChartSource,
    rows: list[dict[str, Any]],
) -> tuple[PoolMasterDataChartSnapshot, dict[str, Any]]:
    fingerprint = _compute_chart_snapshot_fingerprint(rows=rows)
    now = timezone.now()
    snapshot = PoolMasterDataChartSnapshot.objects.create(
        tenant_id=source.tenant_id,
        chart_source=source,
        fingerprint=fingerprint,
        row_count=len(rows),
        metadata={
            "source_database_id": str(source.database_id),
            "chart_identity": str(source.chart_identity),
            "config_name": str(source.config_name),
            "config_version": str(source.config_version),
            "generated_at": now.isoformat(),
        },
    )

    created_count = 0
    updated_count = 0
    unchanged_count = 0
    expected_ids: set[str] = set()
    with transaction.atomic():
        for row in rows:
            canonical_id = _build_gl_account_canonical_id(chart_identity=row["chart_identity"], code=row["code"])
            expected_ids.add(canonical_id)
            existing = PoolMasterGLAccount.objects.filter(
                tenant_id=source.tenant_id,
                canonical_id=canonical_id,
            ).first()
            metadata = _build_gl_account_metadata(
                existing_metadata=dict(existing.metadata or {}) if existing is not None else {},
                source=source,
                snapshot_fingerprint=fingerprint,
                row=row,
            )
            result = upsert_pool_master_data_gl_account(
                tenant_id=source.tenant_id,
                canonical_id=canonical_id,
                code=row["code"],
                name=row["name"],
                chart_identity=row["chart_identity"],
                config_name=row["config_name"],
                config_version=row["config_version"],
                metadata=metadata,
                existing=existing,
                origin_system="cc",
            )
            account = result.entity
            resurrected = False
            if account.is_retired or account.retired_at is not None:
                account.is_retired = False
                account.retired_at = None
                account.save(update_fields=["is_retired", "retired_at", "updated_at"])
                resurrected = True

            if result.created:
                created_count += 1
            elif result.changed or resurrected:
                updated_count += 1
            else:
                unchanged_count += 1

        retired_accounts = list(
            PoolMasterGLAccount.objects.filter(
                tenant_id=source.tenant_id,
                chart_identity=source.chart_identity,
                config_name=source.config_name,
                config_version=source.config_version,
                is_retired=False,
            ).exclude(canonical_id__in=expected_ids)
        )
        retired_count = 0
        for account in retired_accounts:
            metadata = dict(account.metadata or {})
            chart_metadata = dict(metadata.get(_CHART_PROVENANCE_KEY) or {})
            chart_metadata.update(
                {
                    "retired": True,
                    "retired_at": now.isoformat(),
                    "retired_by_snapshot_fingerprint": fingerprint,
                }
            )
            metadata[_CHART_PROVENANCE_KEY] = chart_metadata
            account.metadata = metadata
            account.is_retired = True
            account.retired_at = now
            account.save(update_fields=["metadata", "is_retired", "retired_at", "updated_at"])
            retired_count += 1

    snapshot.materialized_count = created_count
    snapshot.updated_count = updated_count
    snapshot.unchanged_count = unchanged_count
    snapshot.retired_count = retired_count
    snapshot.save(
        update_fields=[
            "materialized_count",
            "updated_count",
            "unchanged_count",
            "retired_count",
        ]
    )

    source.status = PoolMasterDataChartSourceStatus.ACTIVE
    source.last_success_at = now
    source.last_error_code = ""
    source.last_error = ""
    source.save(update_fields=["status", "last_success_at", "last_error_code", "last_error", "updated_at"])

    return snapshot, {
        "rows_total": len(rows),
        "fingerprint": fingerprint,
        "created_count": created_count,
        "updated_count": updated_count,
        "unchanged_count": unchanged_count,
        "retired_count": retired_count,
        "compatibility_class": {
            "chart_identity": str(source.chart_identity),
            "config_name": str(source.config_name),
            "config_version": str(source.config_version),
        },
    }


def _run_follower_resolution(
    *,
    job: PoolMasterDataChartMaterializationJob,
    source: PoolMasterDataChartSource,
    snapshot: PoolMasterDataChartSnapshot,
    mode: str,
    database_ids: Iterable[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    compatible_databases = _resolve_compatible_databases(source=source, database_ids=database_ids)
    canonical_accounts = list(
        PoolMasterGLAccount.objects.filter(
            tenant_id=source.tenant_id,
            chart_identity=source.chart_identity,
            config_name=source.config_name,
            config_version=source.config_version,
            is_retired=False,
        ).order_by("code", "canonical_id")
    )
    totals = {
        "database_count": len(compatible_databases),
        "ok_count": 0,
        "backfilled_count": 0,
        "missing_count": 0,
        "ambiguous_count": 0,
        "stale_count": 0,
    }
    diagnostics: dict[str, Any] = {"databases": []}
    PoolMasterDataChartFollowerStatus.objects.filter(job=job).delete()

    for database in compatible_databases:
        existing_bindings = {
            str(binding.canonical_id): binding
            for binding in PoolMasterDataBinding.objects.filter(
                tenant_id=source.tenant_id,
                database_id=database.id,
                entity_type="gl_account",
                chart_identity=source.chart_identity,
                canonical_id__in=[str(account.canonical_id) for account in canonical_accounts],
            )
        }
        follower_preflight = None
        try:
            follower_preflight = run_pool_master_data_bootstrap_source_preflight(
                tenant_id=str(source.tenant_id),
                database=database,
                entity_scope=["gl_account"],
            )
            if not follower_preflight.ok:
                first_error = (follower_preflight.errors or [{}])[0]
                verdict = PoolMasterDataChartFollowerVerdict.MISSING
                detail = str(first_error.get("detail") or "Follower chart preflight failed.")
                follower_status = PoolMasterDataChartFollowerStatus.objects.create(
                    tenant_id=source.tenant_id,
                    job=job,
                    snapshot=snapshot,
                    database=database,
                    verdict=verdict,
                    detail=detail,
                    diagnostics={
                        "preflight": sanitize_master_data_sync_value(
                            {
                                "errors": list(follower_preflight.errors or []),
                                "diagnostics": dict(follower_preflight.diagnostics or {}),
                            }
                        )
                    },
                )
                totals["missing_count"] += 1
                diagnostics["databases"].append(
                    sanitize_master_data_sync_value(serialize_pool_master_data_chart_follower_status(follower_status))
                )
                continue

            raw_rows = fetch_pool_master_data_bootstrap_source_rows(
                tenant_id=str(source.tenant_id),
                database=database,
                entity_type="gl_account",
            )
        except Exception as exc:
            follower_status = PoolMasterDataChartFollowerStatus.objects.create(
                tenant_id=source.tenant_id,
                job=job,
                snapshot=snapshot,
                database=database,
                verdict=PoolMasterDataChartFollowerVerdict.MISSING,
                detail=sanitize_master_data_sync_text(str(exc) or "Follower chart fetch failed."),
                diagnostics={"error": sanitize_master_data_sync_text(str(exc))},
            )
            totals["missing_count"] += 1
            diagnostics["databases"].append(
                sanitize_master_data_sync_value(serialize_pool_master_data_chart_follower_status(follower_status))
            )
            continue

        row_index: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in raw_rows:
            row_chart_identity = str(row.get("chart_identity") or "").strip()
            if _normalize_chart_identity(row_chart_identity) != _normalize_chart_identity(source.chart_identity):
                continue
            row_code = str(row.get("code") or "").strip()
            row_name = str(row.get("name") or "").strip()
            if not row_code or not row_name:
                continue
            row_index[_normalize_code(row_code)].append(
                {
                    "code": row_code,
                    "name": row_name,
                    "chart_identity": row_chart_identity,
                    "source_ref": _read_row_source_ref(row=row, fallback=row_code),
                }
            )

        matched_accounts = 0
        missing_accounts = 0
        ambiguous_accounts = 0
        stale_bindings = 0
        backfilled_accounts = 0
        unresolved_diagnostics: list[dict[str, Any]] = []
        for account in canonical_accounts:
            matches = row_index.get(_normalize_code(account.code), [])
            if not matches:
                missing_accounts += 1
                unresolved_diagnostics.append(
                    {
                        "code": "FOLLOWER_GL_ACCOUNT_MISSING",
                        "detail": f"Follower database does not contain GLAccount code '{account.code}'.",
                        "canonical_id": str(account.canonical_id),
                        "database_id": str(database.id),
                        "entity_type": "gl_account",
                    }
                )
                continue
            if len(matches) > 1:
                ambiguous_accounts += 1
                unresolved_diagnostics.append(
                    {
                        "code": "FOLLOWER_GL_ACCOUNT_AMBIGUOUS",
                        "detail": f"Follower database resolves GLAccount code '{account.code}' ambiguously.",
                        "canonical_id": str(account.canonical_id),
                        "database_id": str(database.id),
                        "entity_type": "gl_account",
                        "matches": sanitize_master_data_sync_value(matches),
                    }
                )
                continue
            match = matches[0]
            binding = existing_bindings.get(str(account.canonical_id))
            if binding is None:
                if mode == PoolMasterDataChartMaterializationMode.BACKFILL_BINDINGS:
                    upsert_pool_master_data_binding(
                        tenant=database.tenant,
                        entity_type="gl_account",
                        canonical_id=str(account.canonical_id),
                        database=database,
                        ib_ref_key=str(match["source_ref"]),
                        chart_identity=str(source.chart_identity),
                        sync_status=PoolMasterBindingSyncStatus.RESOLVED,
                        fingerprint=_build_binding_fingerprint(database_id=str(database.id), row=match),
                        metadata={
                            _CHART_PROVENANCE_KEY: {
                                "chart_source_id": str(source.id),
                                "chart_snapshot_id": str(snapshot.id),
                                "source_database_id": str(source.database_id),
                                "resolved_from_database_id": str(database.id),
                                "resolved_ref_key": str(match["source_ref"]),
                            }
                        },
                        origin_system="cc",
                    )
                    backfilled_accounts += 1
                    continue
                missing_accounts += 1
                unresolved_diagnostics.append(
                    {
                        "code": "FOLLOWER_GL_ACCOUNT_BINDING_MISSING",
                        "detail": f"Follower database requires GLAccount binding for code '{account.code}'.",
                        "canonical_id": str(account.canonical_id),
                        "database_id": str(database.id),
                        "entity_type": "gl_account",
                    }
                )
                continue
            if str(binding.ib_ref_key or "").strip() != str(match["source_ref"]):
                stale_bindings += 1
                unresolved_diagnostics.append(
                    {
                        "code": "FOLLOWER_GL_ACCOUNT_BINDING_STALE",
                        "detail": f"Follower binding for code '{account.code}' points to stale Ref_Key.",
                        "canonical_id": str(account.canonical_id),
                        "database_id": str(database.id),
                        "entity_type": "gl_account",
                        "expected_ref_key": str(match["source_ref"]),
                        "actual_ref_key": str(binding.ib_ref_key or ""),
                    }
                )
                continue
            matched_accounts += 1

        verdict = PoolMasterDataChartFollowerVerdict.OK
        detail = "Follower coverage is aligned."
        if ambiguous_accounts > 0:
            verdict = PoolMasterDataChartFollowerVerdict.AMBIGUOUS
            detail = "Follower coverage is ambiguous and requires manual remediation."
        elif stale_bindings > 0:
            verdict = PoolMasterDataChartFollowerVerdict.STALE
            detail = "Follower bindings are stale and require manual remediation."
        elif missing_accounts > 0:
            verdict = PoolMasterDataChartFollowerVerdict.MISSING
            detail = "Follower coverage is incomplete."
        elif backfilled_accounts > 0:
            verdict = PoolMasterDataChartFollowerVerdict.BACKFILLED
            detail = "Follower bindings were backfilled automatically."

        follower_status = PoolMasterDataChartFollowerStatus.objects.create(
            tenant_id=source.tenant_id,
            job=job,
            snapshot=snapshot,
            database=database,
            verdict=verdict,
            detail=detail,
            matched_accounts=matched_accounts,
            missing_accounts=missing_accounts,
            ambiguous_accounts=ambiguous_accounts,
            stale_bindings=stale_bindings,
            backfilled_accounts=backfilled_accounts,
            diagnostics={
                "preflight": sanitize_master_data_sync_value(
                    {
                        "coverage": dict((follower_preflight.coverage or {}) if follower_preflight is not None else {}),
                        "diagnostics": dict((follower_preflight.diagnostics or {}) if follower_preflight is not None else {}),
                    }
                ),
                "issues": unresolved_diagnostics,
            },
        )
        if verdict == PoolMasterDataChartFollowerVerdict.OK:
            totals["ok_count"] += 1
        elif verdict == PoolMasterDataChartFollowerVerdict.BACKFILLED:
            totals["backfilled_count"] += 1
        elif verdict == PoolMasterDataChartFollowerVerdict.AMBIGUOUS:
            totals["ambiguous_count"] += 1
        elif verdict == PoolMasterDataChartFollowerVerdict.STALE:
            totals["stale_count"] += 1
        else:
            totals["missing_count"] += 1
        diagnostics["databases"].append(
            sanitize_master_data_sync_value(serialize_pool_master_data_chart_follower_status(follower_status))
        )

    totals["resolved_database_ids"] = [str(database.id) for database in compatible_databases]
    return sanitize_master_data_sync_value(totals), sanitize_master_data_sync_value(diagnostics)


def _require_latest_snapshot(*, source: PoolMasterDataChartSource) -> PoolMasterDataChartSnapshot:
    snapshot = source.snapshots.order_by("-created_at").first()
    if snapshot is None:
        raise ValueError(
            f"{CHART_SOURCE_ROWS_EMPTY}: chart materialization requires a successful snapshot before follower verification"
        )
    return snapshot


def _resolve_compatible_databases(
    *,
    source: PoolMasterDataChartSource,
    database_ids: Iterable[str] | None = None,
) -> list[Database]:
    requested_ids = {str(item).strip() for item in (database_ids or []) if str(item).strip()}
    queryset = Database.objects.filter(tenant_id=source.tenant_id).exclude(id=source.database_id)
    if requested_ids:
        queryset = queryset.filter(id__in=requested_ids)
    result: list[Database] = []
    for database in queryset.order_by("name", "id"):
        profile = get_business_configuration_profile(database=database) or {}
        if (
            str(profile.get("config_name") or "").strip() == str(source.config_name).strip()
            and str(profile.get("config_version") or "").strip() == str(source.config_version).strip()
        ):
            result.append(database)
    return result


def _serialize_candidate_databases(*, source: PoolMasterDataChartSource) -> list[dict[str, Any]]:
    rows = []
    for database in _resolve_compatible_databases(source=source):
        rows.append(
            {
                "database_id": str(database.id),
                "database_name": str(database.name or ""),
                "cluster_id": str(database.cluster_id) if getattr(database, "cluster_id", None) else None,
            }
        )
    return rows


def _require_business_profile(*, database: Database) -> dict[str, Any]:
    profile = get_business_configuration_profile(database=database) or {}
    config_name = str(profile.get("config_name") or "").strip()
    config_version = str(profile.get("config_version") or "").strip()
    if not config_name or not config_version:
        raise ValueError(
            f"{CHART_SOURCE_BUSINESS_PROFILE_MISSING}: database '{database.id}' does not have a verified business configuration profile"
        )
    return {
        "config_name": config_name,
        "config_version": config_version,
        "verification_status": str(profile.get("verification_status") or ""),
        "verified_at": str(profile.get("verified_at") or ""),
    }


def _build_gl_account_metadata(
    *,
    existing_metadata: Mapping[str, Any] | None,
    source: PoolMasterDataChartSource,
    snapshot_fingerprint: str,
    row: Mapping[str, Any],
) -> dict[str, Any]:
    metadata = dict(existing_metadata or {})
    chart_metadata = dict(metadata.get(_CHART_PROVENANCE_KEY) or {})
    chart_metadata.update(
        {
            "chart_source_id": str(source.id),
            "source_database_id": str(source.database_id),
            "source_database_name": str(source.database.name or ""),
            "source_snapshot_fingerprint": str(snapshot_fingerprint or ""),
            "source_ref": str(row.get("source_ref") or ""),
            "source_canonical_id": str(row.get("source_canonical_id") or ""),
            "compatibility_class": {
                "chart_identity": str(source.chart_identity),
                "config_name": str(source.config_name),
                "config_version": str(source.config_version),
            },
            "materialized_at": timezone.now().isoformat(),
            "retired": False,
        }
    )
    metadata[_CHART_PROVENANCE_KEY] = chart_metadata
    return sanitize_master_data_sync_value(metadata)


def _build_gl_account_canonical_id(*, chart_identity: str, code: str) -> str:
    normalized_chart = _normalize_chart_identity(chart_identity)
    normalized_code = _normalize_code(code)
    payload = f"{normalized_chart}|{normalized_code}".encode("utf-8")
    digest = hashlib.sha1(payload).hexdigest()[:20]
    return f"gl-account-{digest}"


def _compute_chart_snapshot_fingerprint(*, rows: list[dict[str, Any]]) -> str:
    payload = [
        {
            "code": _normalize_code(item["code"]),
            "name": str(item["name"]).strip(),
            "chart_identity": _normalize_chart_identity(item["chart_identity"]),
            "source_ref": str(item["source_ref"]).strip(),
        }
        for item in rows
    ]
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _build_binding_fingerprint(*, database_id: str, row: Mapping[str, Any]) -> str:
    payload = {
        "database_id": str(database_id or "").strip(),
        "code": _normalize_code(str(row.get("code") or "")),
        "chart_identity": _normalize_chart_identity(str(row.get("chart_identity") or "")),
        "source_ref": str(row.get("source_ref") or "").strip(),
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _normalize_chart_identity(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _normalize_code(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip()).upper()


def _read_row_source_ref(*, row: Mapping[str, Any], fallback: str) -> str:
    for key in ("source_ref", "ref_key", "Ref_Key", "canonical_id"):
        token = str(row.get(key) or "").strip()
        if token:
            return token
    return str(fallback or "").strip()


def _normalize_job_mode(mode: str) -> str:
    normalized = str(mode or "").strip()
    choices = {choice for choice, _label in PoolMasterDataChartMaterializationMode.choices}
    if normalized not in choices:
        raise ValueError(f"{CHART_JOB_MODE_INVALID}: unsupported chart materialization mode '{mode}'")
    return normalized


def _append_job_audit(
    *,
    job: PoolMasterDataChartMaterializationJob,
    action: str,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    audit_trail = list(job.audit_trail or [])
    audit_trail.append(
        sanitize_master_data_sync_value(
            {
                "action": str(action or "").strip(),
                "at": timezone.now().isoformat(),
                "metadata": dict(metadata or {}),
            }
        )
    )
    job.audit_trail = audit_trail


def _build_bindings_remediation_href(*, diagnostics: Mapping[str, Any]) -> str | None:
    issues = diagnostics.get("issues")
    if not isinstance(issues, list):
        return None
    for issue in issues:
        if not isinstance(issue, Mapping):
            continue
        database_id = str(issue.get("database_id") or "").strip()
        canonical_id = str(issue.get("canonical_id") or "").strip()
        if not database_id:
            continue
        params = [("tab", "bindings"), ("entityType", "gl_account"), ("databaseId", database_id)]
        if canonical_id:
            params.append(("canonicalId", canonical_id))
        return "/pools/master-data?" + "&".join(f"{key}={value}" for key, value in params)
    return None


def _merge_source_metadata(base: Mapping[str, Any] | None, extra: Mapping[str, Any] | None) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in dict(extra or {}).items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _merge_source_metadata(merged.get(key), value)
        else:
            merged[key] = value
    return sanitize_master_data_sync_value(merged)


def _resolve_chart_job_error(exc: Exception) -> tuple[str, str, dict[str, Any]]:
    if isinstance(exc, MasterDataCanonicalUpsertError):
        return exc.code, exc.detail, {}
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            return "VALIDATION_ERROR", "Chart materialization validation failed.", {"errors": exc.message_dict}
        return "VALIDATION_ERROR", "Chart materialization validation failed.", {"errors": str(exc)}
    detail = sanitize_master_data_sync_text(str(exc) or "Chart materialization failed.")
    code = "CHART_MATERIALIZATION_FAILED"
    if ":" in detail:
        maybe_code, maybe_detail = detail.split(":", 1)
        normalized_code = str(maybe_code or "").strip()
        normalized_detail = str(maybe_detail or "").strip()
        if normalized_code:
            code = normalized_code
            detail = normalized_detail or detail
    return code, detail, {"exception": detail}


__all__ = [
    "CHART_JOB_NOT_FOUND",
    "CHART_SOURCE_BUSINESS_PROFILE_MISMATCH",
    "CHART_SOURCE_BUSINESS_PROFILE_MISSING",
    "CHART_SOURCE_CHART_IDENTITY_REQUIRED",
    "CHART_SOURCE_DATABASE_NOT_FOUND",
    "CHART_SOURCE_DATABASE_TENANT_MISMATCH",
    "CHART_SOURCE_NOT_FOUND",
    "CHART_SOURCE_PREFLIGHT_FAILED",
    "CHART_SOURCE_ROWS_EMPTY",
    "create_pool_master_data_chart_job",
    "get_pool_master_data_chart_job",
    "list_pool_master_data_chart_jobs",
    "list_pool_master_data_chart_sources",
    "serialize_pool_master_data_chart_job",
    "serialize_pool_master_data_chart_source",
    "upsert_pool_master_data_chart_source",
]
