from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.databases.models import Database
from apps.tenancy.models import Tenant

from .business_configuration_profile import get_business_configuration_profile
from .master_data_canonical_upsert import MasterDataCanonicalUpsertError
from .master_data_bindings import upsert_pool_master_data_binding
from .master_data_bootstrap_import_dependency_order import (
    BOOTSTRAP_DEPENDENCY_DECISION_DEFERRED,
    BOOTSTRAP_DEPENDENCY_DECISION_FAILED,
    evaluate_binding_dependency,
    evaluate_contract_dependency,
    resolve_bootstrap_import_dependency_order,
)
from .master_data_bootstrap_import_idempotency import (
    BOOTSTRAP_CHUNK_RESUME_ACTION_BLOCKED,
    BOOTSTRAP_CHUNK_RESUME_ACTION_EXECUTE,
    BOOTSTRAP_CHUNK_RESUME_ACTION_RETRY,
    BOOTSTRAP_CHUNK_RESUME_ACTION_SKIP,
    build_bootstrap_import_chunk_idempotency_key,
    resolve_bootstrap_import_chunk_resume_action,
)
from .master_data_bootstrap_import_lifecycle_contract import (
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_DRY_RUN,
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_EXECUTE,
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_FINALIZE,
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_PREFLIGHT,
    resolve_bootstrap_import_next_status,
)
from .master_data_registry import normalize_pool_master_data_entity_type
from .master_data_bootstrap_import_source_adapter import (
    PoolMasterDataBootstrapSourcePreflightResult,
    fetch_pool_master_data_bootstrap_source_rows,
    run_pool_master_data_bootstrap_source_preflight,
)
from .master_data_bootstrap_import_runtime import (
    start_pool_master_data_bootstrap_import_job_execution,
)
from .master_data_dedupe import (
    MASTER_DATA_DEDUPE_REVIEW_REQUIRED,
    MasterDataDedupeReviewRequiredError,
    ingest_pool_master_data_source_record,
)
from .master_data_sync_redaction import sanitize_master_data_sync_text, sanitize_master_data_sync_value
from .models import (
    PoolMasterBindingSyncStatus,
    PoolMasterContract,
    PoolMasterDataBootstrapImportChunk,
    PoolMasterDataBootstrapImportChunkStatus,
    PoolMasterDataBootstrapImportEntityType,
    PoolMasterDataEntityType,
    PoolMasterDataBootstrapImportJob,
    PoolMasterDataBootstrapImportJobStatus,
    PoolMasterDataBootstrapImportReport,
    PoolMasterGLAccount,
    PoolMasterItem,
    PoolMasterParty,
    PoolMasterTaxProfile,
)


BOOTSTRAP_IMPORT_MODE_DRY_RUN = "dry_run"
BOOTSTRAP_IMPORT_MODE_EXECUTE = "execute"

BOOTSTRAP_IMPORT_JOB_NOT_FOUND = "BOOTSTRAP_IMPORT_JOB_NOT_FOUND"
BOOTSTRAP_IMPORT_MODE_INVALID = "BOOTSTRAP_IMPORT_MODE_INVALID"
BOOTSTRAP_IMPORT_SCOPE_EMPTY = "BOOTSTRAP_IMPORT_SCOPE_EMPTY"
BOOTSTRAP_IMPORT_DATABASE_NOT_FOUND = "BOOTSTRAP_IMPORT_DATABASE_NOT_FOUND"
BOOTSTRAP_IMPORT_DATABASE_TENANT_MISMATCH = "BOOTSTRAP_IMPORT_DATABASE_TENANT_MISMATCH"
BOOTSTRAP_IMPORT_ROW_REQUIRED_FIELD = "BOOTSTRAP_IMPORT_ROW_REQUIRED_FIELD"
BOOTSTRAP_IMPORT_ROW_INVALID = "BOOTSTRAP_IMPORT_ROW_INVALID"
BOOTSTRAP_IMPORT_CONTRACT_OWNER_NOT_FOUND = "BOOTSTRAP_IMPORT_CONTRACT_OWNER_NOT_FOUND"
BOOTSTRAP_IMPORT_BINDING_TARGET_INVALID = "BOOTSTRAP_IMPORT_BINDING_TARGET_INVALID"
BOOTSTRAP_IMPORT_BINDING_REF_REQUIRED = "BOOTSTRAP_IMPORT_BINDING_REF_REQUIRED"
BOOTSTRAP_IMPORT_CANCELED = "BOOTSTRAP_IMPORT_CANCELED"
BOOTSTRAP_IMPORT_ASYNC_EXECUTOR_UNAVAILABLE = "BOOTSTRAP_IMPORT_ASYNC_EXECUTOR_UNAVAILABLE"
BOOTSTRAP_IMPORT_EXECUTE_IN_PROGRESS = "BOOTSTRAP_IMPORT_EXECUTE_IN_PROGRESS"
BOOTSTRAP_IMPORT_PREFLIGHT_FAILED = "BOOTSTRAP_IMPORT_PREFLIGHT_FAILED"

_TERMINAL_JOB_STATUSES = {
    PoolMasterDataBootstrapImportJobStatus.FINALIZED,
    PoolMasterDataBootstrapImportJobStatus.FAILED,
    PoolMasterDataBootstrapImportJobStatus.CANCELED,
}

@dataclass(frozen=True)
class BootstrapRowOutcome:
    action: str
    canonical_id: str = ""
    source_canonical_id: str = ""
    error_code: str = ""
    detail: str = ""
    review_item_id: str = ""


class _BootstrapExecutionCanceled(RuntimeError):
    pass


class BootstrapImportPreflightBlockedError(ValueError):
    def __init__(
        self,
        *,
        error_code: str,
        detail: str,
        preflight_result: dict[str, Any],
    ) -> None:
        self.error_code = str(error_code or "").strip() or BOOTSTRAP_IMPORT_PREFLIGHT_FAILED
        self.detail = str(detail or "").strip() or "Bootstrap preflight failed."
        self.preflight_result = sanitize_master_data_sync_value(dict(preflight_result or {}))
        super().__init__(f"{self.error_code}: {self.detail}")


def run_pool_master_data_bootstrap_preflight_preview(
    *,
    tenant_id: str,
    database: Database,
    entity_scope: list[str],
    actor_id: str = "",
) -> dict[str, Any]:
    normalized_scope = _normalize_entity_scope(entity_scope)
    preflight = run_pool_master_data_bootstrap_source_preflight(
        tenant_id=tenant_id,
        database=database,
        entity_scope=normalized_scope,
        actor_id=actor_id,
    )
    return _serialize_preflight_result(preflight=preflight, entity_scope=normalized_scope)


def run_pool_master_data_bootstrap_dry_run_preview(
    *,
    tenant_id: str,
    database: Database,
    entity_scope: list[str],
    actor_id: str = "",
    chunk_size: int = 200,
) -> dict[str, Any]:
    normalized_scope = _normalize_entity_scope(entity_scope)
    rows_by_entity = _fetch_rows_for_scope(
        tenant_id=tenant_id,
        database=database,
        entity_scope=normalized_scope,
        actor_id=actor_id,
    )
    return _build_dry_run_summary(
        rows_by_entity=rows_by_entity,
        chunk_size=int(_safe_chunk_size(chunk_size)),
    )


def create_pool_master_data_bootstrap_import_job(
    *,
    tenant: Tenant,
    database: Database,
    entity_scope: list[str],
    mode: str,
    actor_id: str,
    chunk_size: int = 200,
) -> PoolMasterDataBootstrapImportJob:
    normalized_mode = _normalize_mode(mode)
    normalized_scope = _normalize_entity_scope(entity_scope)
    if str(database.tenant_id) != str(tenant.id):
        raise ValueError(
            f"{BOOTSTRAP_IMPORT_DATABASE_TENANT_MISMATCH}: "
            f"database '{database.id}' does not belong to tenant '{tenant.id}'"
        )
    preflight_preview: PoolMasterDataBootstrapSourcePreflightResult | None = None
    if normalized_mode == BOOTSTRAP_IMPORT_MODE_EXECUTE:
        preflight_preview = run_pool_master_data_bootstrap_source_preflight(
            tenant_id=str(tenant.id),
            database=database,
            entity_scope=normalized_scope,
            actor_id=actor_id,
        )
        if not preflight_preview.ok:
            first_error = preflight_preview.errors[0] if preflight_preview.errors else {}
            raise BootstrapImportPreflightBlockedError(
                error_code=str(first_error.get("code") or BOOTSTRAP_IMPORT_PREFLIGHT_FAILED),
                detail=str(first_error.get("detail") or "Bootstrap preflight failed."),
                preflight_result=_serialize_preflight_result(
                    preflight=preflight_preview,
                    entity_scope=normalized_scope,
                ),
            )

    job = PoolMasterDataBootstrapImportJob.objects.create(
        tenant=tenant,
        database=database,
        entity_scope=normalized_scope,
        status=PoolMasterDataBootstrapImportJobStatus.PREFLIGHT_PENDING,
        metadata={
            "source_kind": "ib_odata",
            "chunk_size": int(_safe_chunk_size(chunk_size)),
            "mode": normalized_mode,
        },
    )
    PoolMasterDataBootstrapImportReport.objects.get_or_create(job=job)
    _append_job_audit(
        job=job,
        action="job_created",
        actor_id=actor_id,
        metadata={
            "mode": normalized_mode,
            "entity_scope": normalized_scope,
            "database_id": str(database.id),
        },
    )

    preflight_result = _run_job_preflight_step(
        job=job,
        actor_id=actor_id,
        preflight_override=preflight_preview,
    )
    if not preflight_result.ok:
        return _refresh_job(job_id=str(job.id))

    _run_job_dry_run_step(job=job, actor_id=actor_id)
    job = _refresh_job(job_id=str(job.id))
    if job.status == PoolMasterDataBootstrapImportJobStatus.DRY_RUN_FAILED:
        return job

    if normalized_mode == BOOTSTRAP_IMPORT_MODE_EXECUTE:
        _enqueue_bootstrap_import_job_execution(
            job=job,
            actor_id=actor_id,
            retry_failed_only=False,
        )
    return _refresh_job(job_id=str(job.id))


def list_pool_master_data_bootstrap_import_jobs(
    *,
    tenant_id: str,
    database_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[PoolMasterDataBootstrapImportJob], int]:
    queryset = PoolMasterDataBootstrapImportJob.objects.filter(tenant_id=str(tenant_id or "").strip())
    if database_id:
        queryset = queryset.filter(database_id=str(database_id).strip())
    total = queryset.count()
    rows = list(
        queryset.select_related("database")
        .prefetch_related("report")
        .order_by("-created_at")[max(0, offset) : max(0, offset) + max(1, limit)]
    )
    return rows, total


def get_pool_master_data_bootstrap_import_job(
    *,
    tenant_id: str,
    job_id: str,
) -> PoolMasterDataBootstrapImportJob:
    return _get_job_or_raise(tenant_id=tenant_id, job_id=job_id)


def cancel_pool_master_data_bootstrap_import_job(
    *,
    tenant_id: str,
    job_id: str,
    actor_id: str,
) -> PoolMasterDataBootstrapImportJob:
    job = _get_job_or_raise(tenant_id=tenant_id, job_id=job_id)
    if job.status in _TERMINAL_JOB_STATUSES:
        _append_job_audit(
            job=job,
            action="cancel_skipped_terminal",
            actor_id=actor_id,
            metadata={"status": str(job.status)},
        )
        return _refresh_job(job_id=str(job.id))

    now = timezone.now()
    job.status = PoolMasterDataBootstrapImportJobStatus.CANCELED
    job.last_error_code = BOOTSTRAP_IMPORT_CANCELED
    job.last_error = "Bootstrap import canceled by operator."
    job.finished_at = now
    _append_job_audit(
        job=job,
        action="job_canceled",
        actor_id=actor_id,
        metadata={"at": now.isoformat()},
    )
    job.save(
        update_fields=[
            "status",
            "last_error_code",
            "last_error",
            "finished_at",
            "metadata",
            "updated_at",
        ]
    )
    PoolMasterDataBootstrapImportChunk.objects.filter(
        job=job,
        status__in=[
            PoolMasterDataBootstrapImportChunkStatus.PENDING,
            PoolMasterDataBootstrapImportChunkStatus.RUNNING,
            PoolMasterDataBootstrapImportChunkStatus.DEFERRED,
        ],
    ).update(
        status=PoolMasterDataBootstrapImportChunkStatus.CANCELED,
        last_error_code=BOOTSTRAP_IMPORT_CANCELED,
        last_error="Chunk canceled by operator.",
        finished_at=now,
        updated_at=now,
    )
    _rebuild_report_and_progress(job=job)
    return _refresh_job(job_id=str(job.id))


def retry_failed_pool_master_data_bootstrap_import_chunks(
    *,
    tenant_id: str,
    job_id: str,
    actor_id: str,
) -> PoolMasterDataBootstrapImportJob:
    job = _get_job_or_raise(tenant_id=tenant_id, job_id=job_id)
    if job.status in {
        PoolMasterDataBootstrapImportJobStatus.EXECUTE_PENDING,
        PoolMasterDataBootstrapImportJobStatus.RUNNING,
    }:
        raise ValueError(
            f"{BOOTSTRAP_IMPORT_EXECUTE_IN_PROGRESS}: "
            f"bootstrap import job '{job.id}' is already in progress"
        )
    failed_chunk_count = PoolMasterDataBootstrapImportChunk.objects.filter(
        job=job,
        status__in=[
            PoolMasterDataBootstrapImportChunkStatus.FAILED,
            PoolMasterDataBootstrapImportChunkStatus.DEFERRED,
        ],
    ).count()
    if failed_chunk_count == 0:
        _append_job_audit(
            job=job,
            action="retry_failed_chunks_noop",
            actor_id=actor_id,
            metadata={"reason": "no_failed_chunks"},
        )
        return _refresh_job(job_id=str(job.id))

    job.status = PoolMasterDataBootstrapImportJobStatus.EXECUTE_PENDING
    job.finished_at = None
    job.last_error_code = ""
    job.last_error = ""
    _append_job_audit(
        job=job,
        action="retry_failed_chunks_requested",
        actor_id=actor_id,
        metadata={"failed_chunks": failed_chunk_count},
    )
    job.save(
        update_fields=[
            "status",
            "finished_at",
            "last_error_code",
            "last_error",
            "metadata",
            "updated_at",
        ]
    )
    _enqueue_bootstrap_import_job_execution(
        job=job,
        actor_id=actor_id,
        retry_failed_only=True,
    )
    return _refresh_job(job_id=str(job.id))


def run_pool_master_data_bootstrap_import_job_execution(
    *,
    job_id: str,
    actor_id: str,
    retry_failed_only: bool,
) -> None:
    job = _refresh_job(job_id=str(job_id))
    if job.status in _TERMINAL_JOB_STATUSES:
        return
    if job.status != PoolMasterDataBootstrapImportJobStatus.EXECUTE_PENDING:
        return
    _run_job_execute_step(
        job=job,
        actor_id=actor_id,
        retry_failed_only=retry_failed_only,
    )


def _enqueue_bootstrap_import_job_execution(
    *,
    job: PoolMasterDataBootstrapImportJob,
    actor_id: str,
    retry_failed_only: bool,
) -> None:
    enqueued = start_pool_master_data_bootstrap_import_job_execution(
        job_id=str(job.id),
        actor_id=actor_id,
        retry_failed_only=retry_failed_only,
    )
    if not enqueued:
        now = timezone.now()
        job = _refresh_job(job_id=str(job.id))
        job.status = PoolMasterDataBootstrapImportJobStatus.FAILED
        job.finished_at = now
        job.last_error_code = BOOTSTRAP_IMPORT_ASYNC_EXECUTOR_UNAVAILABLE
        job.last_error = "Bootstrap import async executor is unavailable."
        _append_job_audit(
            job=job,
            action="execute_enqueue_failed",
            actor_id=actor_id,
            metadata={"retry_failed_only": bool(retry_failed_only)},
        )
        job.save(
            update_fields=[
                "status",
                "finished_at",
                "last_error_code",
                "last_error",
                "metadata",
                "updated_at",
            ]
        )
        raise ValueError(
            f"{BOOTSTRAP_IMPORT_ASYNC_EXECUTOR_UNAVAILABLE}: bootstrap import async executor is unavailable"
        )

    _append_job_audit(
        job=job,
        action="execute_enqueued",
        actor_id=actor_id,
        metadata={"retry_failed_only": bool(retry_failed_only)},
    )
    job.save(update_fields=["metadata", "updated_at"])


def serialize_pool_master_data_bootstrap_import_job(
    *,
    job: PoolMasterDataBootstrapImportJob,
    include_chunks: bool = False,
) -> dict[str, Any]:
    report = getattr(job, "report", None)
    metadata = job.metadata if isinstance(job.metadata, dict) else {}
    progress = metadata.get("progress")
    progress_dict = dict(progress) if isinstance(progress, dict) else _default_progress()
    payload: dict[str, Any] = {
        "id": str(job.id),
        "tenant_id": str(job.tenant_id),
        "database_id": str(job.database_id),
        "entity_scope": list(job.entity_scope or []),
        "status": str(job.status),
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "last_error_code": str(job.last_error_code or ""),
        "last_error": sanitize_master_data_sync_text(str(job.last_error or "")),
        "preflight_result": _as_dict(metadata.get("preflight_result")),
        "dry_run_summary": _as_dict(metadata.get("dry_run_summary")),
        "progress": progress_dict,
        "audit_trail": _as_list(metadata.get("audit_trail")),
        "report": {
            "created_count": int(getattr(report, "created_count", 0) or 0),
            "updated_count": int(getattr(report, "updated_count", 0) or 0),
            "skipped_count": int(getattr(report, "skipped_count", 0) or 0),
            "failed_count": int(getattr(report, "failed_count", 0) or 0),
            "deferred_count": int(getattr(report, "deferred_count", 0) or 0),
            "diagnostics": sanitize_master_data_sync_value(
                dict(getattr(report, "diagnostics", {}) or {})
            ),
        },
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
    if include_chunks:
        chunks = list(
            job.chunks.order_by("entity_type", "chunk_index").all()
        )
        payload["chunks"] = [_serialize_chunk(chunk) for chunk in chunks]
    return payload


def _serialize_preflight_result(
    *,
    preflight: PoolMasterDataBootstrapSourcePreflightResult,
    entity_scope: list[str],
) -> dict[str, Any]:
    return {
        "ok": bool(preflight.ok),
        "source_kind": str(preflight.source_kind),
        "entity_scope": list(entity_scope),
        "coverage": dict(preflight.coverage),
        "credential_strategy": str(preflight.credential_strategy),
        "errors": list(preflight.errors),
        "diagnostics": sanitize_master_data_sync_value(dict(preflight.diagnostics)),
    }


def _run_job_preflight_step(
    *,
    job: PoolMasterDataBootstrapImportJob,
    actor_id: str,
    preflight_override: PoolMasterDataBootstrapSourcePreflightResult | None = None,
) -> PoolMasterDataBootstrapSourcePreflightResult:
    preflight = preflight_override or run_pool_master_data_bootstrap_source_preflight(
        tenant_id=str(job.tenant_id),
        database=job.database,
        entity_scope=list(job.entity_scope or []),
        actor_id=actor_id,
    )
    metadata = job.metadata if isinstance(job.metadata, dict) else {}
    serialized = _serialize_preflight_result(
        preflight=preflight,
        entity_scope=list(job.entity_scope or []),
    )
    serialized["at"] = timezone.now().isoformat()
    metadata["preflight_result"] = serialized
    next_status = resolve_bootstrap_import_next_status(
        current_status=str(job.status),
        step=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_PREFLIGHT,
        succeeded=bool(preflight.ok),
    )
    job.status = next_status
    if preflight.ok:
        job.last_error_code = ""
        job.last_error = ""
    else:
        first_error = preflight.errors[0] if preflight.errors else {}
        job.last_error_code = str(first_error.get("code") or "BOOTSTRAP_PREFLIGHT_FAILED")
        job.last_error = sanitize_master_data_sync_text(
            str(first_error.get("detail") or "Bootstrap preflight failed.")
        )
    _append_job_audit(
        job=job,
        action="preflight_completed",
        actor_id=actor_id,
        metadata={
            "ok": bool(preflight.ok),
            "error_count": len(preflight.errors),
        },
    )
    job.metadata = metadata
    job.save(update_fields=["status", "last_error_code", "last_error", "metadata", "updated_at"])
    return preflight


def _run_job_dry_run_step(
    *,
    job: PoolMasterDataBootstrapImportJob,
    actor_id: str,
) -> None:
    rows_by_entity = _fetch_rows_for_scope(
        tenant_id=str(job.tenant_id),
        database=job.database,
        entity_scope=list(job.entity_scope or []),
        actor_id=actor_id,
    )
    chunk_size = int(_safe_chunk_size((job.metadata or {}).get("chunk_size")))
    summary = _build_dry_run_summary(
        rows_by_entity=rows_by_entity,
        chunk_size=chunk_size,
    )
    metadata = job.metadata if isinstance(job.metadata, dict) else {}
    metadata["dry_run_summary"] = summary
    next_status = resolve_bootstrap_import_next_status(
        current_status=str(job.status),
        step=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_DRY_RUN,
        succeeded=True,
    )
    job.status = next_status
    job.metadata = metadata
    job.last_error_code = ""
    job.last_error = ""
    _append_job_audit(
        job=job,
        action="dry_run_completed",
        actor_id=actor_id,
        metadata={
            "rows_total": int(summary.get("rows_total") or 0),
            "chunks_total": int(summary.get("chunks_total") or 0),
        },
    )
    job.save(update_fields=["status", "metadata", "last_error_code", "last_error", "updated_at"])


def _run_job_execute_step(
    *,
    job: PoolMasterDataBootstrapImportJob,
    actor_id: str,
    retry_failed_only: bool,
) -> None:
    job_id = str(job.id)
    with transaction.atomic():
        locked_job = PoolMasterDataBootstrapImportJob.objects.select_for_update().get(id=job.id)
        if locked_job.status in _TERMINAL_JOB_STATUSES:
            return
        if locked_job.status != PoolMasterDataBootstrapImportJobStatus.EXECUTE_PENDING:
            return

        now = timezone.now()
        execute_status = resolve_bootstrap_import_next_status(
            current_status=str(locked_job.status),
            step=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_EXECUTE,
            succeeded=True,
        )
        locked_job.status = execute_status
        if locked_job.started_at is None:
            locked_job.started_at = now
        locked_job.last_error_code = ""
        locked_job.last_error = ""
        _append_job_audit(
            job=locked_job,
            action="execute_started",
            actor_id=actor_id,
            metadata={"retry_failed_only": bool(retry_failed_only)},
        )
        locked_job.save(
            update_fields=[
                "status",
                "started_at",
                "last_error_code",
                "last_error",
                "metadata",
                "updated_at",
            ]
        )

    active_job = _refresh_job(job_id=job_id)
    try:
        _execute_chunks(
            job=active_job,
            actor_id=actor_id,
            retry_failed_only=retry_failed_only,
        )
        job = _refresh_job(job_id=job_id)
        if job.status == PoolMasterDataBootstrapImportJobStatus.CANCELED:
            _append_job_audit(
                job=job,
                action="execute_canceled",
                actor_id=actor_id,
                metadata={"retry_failed_only": bool(retry_failed_only)},
            )
            job.save(update_fields=["metadata", "updated_at"])
            return

        finalize_status = resolve_bootstrap_import_next_status(
            current_status=str(job.status),
            step=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_FINALIZE,
            succeeded=True,
        )
        job.status = finalize_status
        job.finished_at = timezone.now()
        _append_job_audit(
            job=job,
            action="execute_completed",
            actor_id=actor_id,
            metadata={"retry_failed_only": bool(retry_failed_only)},
        )
        job.save(update_fields=["status", "finished_at", "metadata", "updated_at"])
    except _BootstrapExecutionCanceled:
        job = _refresh_job(job_id=job_id)
        if job.status != PoolMasterDataBootstrapImportJobStatus.CANCELED:
            job.status = PoolMasterDataBootstrapImportJobStatus.CANCELED
            job.last_error_code = BOOTSTRAP_IMPORT_CANCELED
            job.last_error = "Bootstrap import canceled by operator."
            job.finished_at = timezone.now()
            _append_job_audit(
                job=job,
                action="execute_canceled",
                actor_id=actor_id,
                metadata={"retry_failed_only": bool(retry_failed_only)},
            )
            job.save(
                update_fields=[
                    "status",
                    "finished_at",
                    "last_error_code",
                    "last_error",
                    "metadata",
                    "updated_at",
                ]
            )
    except Exception as exc:  # noqa: BLE001
        job = _refresh_job(job_id=job_id)
        job.status = PoolMasterDataBootstrapImportJobStatus.FAILED
        job.finished_at = timezone.now()
        job.last_error_code = "BOOTSTRAP_EXECUTE_FAILED"
        job.last_error = sanitize_master_data_sync_text(str(exc) or "bootstrap execute failed")
        _append_job_audit(
            job=job,
            action="execute_failed",
            actor_id=actor_id,
            metadata={"detail": str(exc) or "bootstrap execute failed"},
        )
        job.save(
            update_fields=[
                "status",
                "finished_at",
                "last_error_code",
                "last_error",
                "metadata",
                "updated_at",
            ]
        )
    finally:
        _rebuild_report_and_progress(job=_refresh_job(job_id=job_id))


def _execute_chunks(
    *,
    job: PoolMasterDataBootstrapImportJob,
    actor_id: str,
    retry_failed_only: bool,
) -> None:
    _raise_if_job_canceled(job_id=str(job.id))
    rows_by_entity = _fetch_rows_for_scope(
        tenant_id=str(job.tenant_id),
        database=job.database,
        entity_scope=list(job.entity_scope or []),
        actor_id=actor_id,
    )
    chunk_size = int(_safe_chunk_size((job.metadata or {}).get("chunk_size")))
    resolved_ids = _load_resolved_canonical_ids(job=job)
    resolved_aliases = _load_resolved_canonical_aliases()
    ordered_scope = resolve_bootstrap_import_dependency_order(selected_scope=list(job.entity_scope or []))

    for entity_type in ordered_scope:
        _raise_if_job_canceled(job_id=str(job.id))
        rows = rows_by_entity.get(entity_type, [])
        for chunk_index, chunk_rows in enumerate(_chunk_rows(rows=rows, chunk_size=chunk_size)):
            _raise_if_job_canceled(job_id=str(job.id))
            chunk, _ = PoolMasterDataBootstrapImportChunk.objects.get_or_create(
                job=job,
                entity_type=entity_type,
                chunk_index=chunk_index,
                defaults={
                    "status": PoolMasterDataBootstrapImportChunkStatus.PENDING,
                },
            )
            if retry_failed_only and chunk.status not in {
                PoolMasterDataBootstrapImportChunkStatus.FAILED,
                PoolMasterDataBootstrapImportChunkStatus.DEFERRED,
            }:
                continue
            _execute_chunk(
                chunk=chunk,
                rows=chunk_rows,
                resolved_ids=resolved_ids,
                resolved_aliases=resolved_aliases,
                actor_id=actor_id,
            )
        if retry_failed_only:
            deferred = PoolMasterDataBootstrapImportChunk.objects.filter(
                job=job,
                entity_type=entity_type,
                status=PoolMasterDataBootstrapImportChunkStatus.DEFERRED,
            )
            for chunk in deferred:
                _raise_if_job_canceled(job_id=str(job.id))
                rows = rows_by_entity.get(entity_type, [])
                if chunk.chunk_index * chunk_size >= len(rows):
                    continue
                chunk_rows = rows[chunk.chunk_index * chunk_size : (chunk.chunk_index + 1) * chunk_size]
                _execute_chunk(
                    chunk=chunk,
                    rows=chunk_rows,
                    resolved_ids=resolved_ids,
                    actor_id=actor_id,
                )


def _execute_chunk(
    *,
    chunk: PoolMasterDataBootstrapImportChunk,
    rows: list[dict[str, Any]],
    resolved_ids: dict[str, set[str]],
    resolved_aliases: dict[str, dict[str, str]],
    actor_id: str,
) -> None:
    _raise_if_job_canceled(job_id=str(chunk.job_id))
    now = timezone.now()
    recomputed_key = build_bootstrap_import_chunk_idempotency_key(
        job_id=str(chunk.job_id),
        entity_type=str(chunk.entity_type),
        chunk_index=int(chunk.chunk_index),
        rows=rows,
    )
    decision = resolve_bootstrap_import_chunk_resume_action(
        chunk_status=str(chunk.status),
        stored_idempotency_key=str(chunk.idempotency_key or ""),
        recomputed_idempotency_key=recomputed_key,
        attempt_count=int(chunk.attempt_count or 0),
    )
    if decision.action == BOOTSTRAP_CHUNK_RESUME_ACTION_SKIP:
        return
    if decision.action == BOOTSTRAP_CHUNK_RESUME_ACTION_BLOCKED:
        chunk.status = PoolMasterDataBootstrapImportChunkStatus.FAILED
        chunk.last_error_code = str(decision.error_code or "BOOTSTRAP_CHUNK_RESUME_BLOCKED")
        chunk.last_error = sanitize_master_data_sync_text(str(decision.detail or "Chunk resume blocked."))
        chunk.finished_at = now
        chunk.records_total = len(rows)
        diagnostics = dict(chunk.diagnostics or {})
        errors = list(diagnostics.get("errors") or [])
        errors.append(
            {
                "code": str(chunk.last_error_code),
                "detail": str(chunk.last_error),
                "at": now.isoformat(),
            }
        )
        diagnostics["errors"] = errors[-100:]
        chunk.diagnostics = sanitize_master_data_sync_value(diagnostics)
        chunk.save(
            update_fields=[
                "status",
                "records_total",
                "last_error_code",
                "last_error",
                "finished_at",
                "diagnostics",
                "updated_at",
            ]
        )
        return
    if decision.action not in {
        BOOTSTRAP_CHUNK_RESUME_ACTION_EXECUTE,
        BOOTSTRAP_CHUNK_RESUME_ACTION_RETRY,
    }:
        return

    chunk.status = PoolMasterDataBootstrapImportChunkStatus.RUNNING
    chunk.idempotency_key = recomputed_key
    chunk.attempt_count = int(chunk.attempt_count or 0) + 1
    chunk.started_at = now
    chunk.finished_at = None
    chunk.records_total = len(rows)
    chunk.records_created = 0
    chunk.records_updated = 0
    chunk.records_skipped = 0
    chunk.records_failed = 0
    chunk.last_error_code = ""
    chunk.last_error = ""
    chunk.diagnostics = {"errors": []}
    chunk.metadata = {
        **dict(chunk.metadata or {}),
        "last_actor_id": str(actor_id or ""),
        "last_started_at": now.isoformat(),
    }
    chunk.save(
        update_fields=[
            "status",
            "idempotency_key",
            "attempt_count",
            "started_at",
            "finished_at",
            "records_total",
            "records_created",
            "records_updated",
            "records_skipped",
            "records_failed",
            "last_error_code",
            "last_error",
            "diagnostics",
            "metadata",
            "updated_at",
        ]
    )

    errors: list[dict[str, Any]] = []
    try:
        for row_index, row in enumerate(rows):
            _raise_if_job_canceled(job_id=str(chunk.job_id))
            outcome = _apply_row(
                job=chunk.job,
                entity_type=str(chunk.entity_type),
                row=row,
                row_index=row_index,
                chunk_index=int(chunk.chunk_index),
                resolved_ids=resolved_ids,
                resolved_aliases=resolved_aliases,
            )
            if outcome.action == "created":
                chunk.records_created += 1
                _mark_resolved_id(
                    resolved_ids=resolved_ids,
                    entity_type=str(chunk.entity_type),
                    canonical_id=outcome.canonical_id,
                )
                _mark_resolved_alias(
                    resolved_aliases=resolved_aliases,
                    entity_type=str(chunk.entity_type),
                    source_canonical_id=outcome.source_canonical_id,
                    canonical_id=outcome.canonical_id,
                )
                continue
            if outcome.action == "updated":
                chunk.records_updated += 1
                _mark_resolved_id(
                    resolved_ids=resolved_ids,
                    entity_type=str(chunk.entity_type),
                    canonical_id=outcome.canonical_id,
                )
                _mark_resolved_alias(
                    resolved_aliases=resolved_aliases,
                    entity_type=str(chunk.entity_type),
                    source_canonical_id=outcome.source_canonical_id,
                    canonical_id=outcome.canonical_id,
                )
                continue
            if outcome.action == "skipped":
                chunk.records_skipped += 1
                _mark_resolved_id(
                    resolved_ids=resolved_ids,
                    entity_type=str(chunk.entity_type),
                    canonical_id=outcome.canonical_id,
                )
                _mark_resolved_alias(
                    resolved_aliases=resolved_aliases,
                    entity_type=str(chunk.entity_type),
                    source_canonical_id=outcome.source_canonical_id,
                    canonical_id=outcome.canonical_id,
                )
                continue

            chunk.records_failed += 1
            errors.append(
                {
                    "row_index": row_index,
                    "code": str(outcome.error_code or BOOTSTRAP_IMPORT_ROW_INVALID),
                    "detail": sanitize_master_data_sync_text(
                        str(outcome.detail or "Bootstrap row apply failed.")
                    ),
                    "action": str(outcome.action),
                    "review_item_id": str(outcome.review_item_id or ""),
                }
            )
    except _BootstrapExecutionCanceled:
        _mark_chunk_canceled(chunk=chunk)
        raise

    if errors:
        has_only_deferred = all(str(item.get("action")) == "deferred" for item in errors)
        chunk.status = (
            PoolMasterDataBootstrapImportChunkStatus.DEFERRED
            if has_only_deferred
            else PoolMasterDataBootstrapImportChunkStatus.FAILED
        )
        first_error = errors[0]
        chunk.last_error_code = str(first_error.get("code") or BOOTSTRAP_IMPORT_ROW_INVALID)
        chunk.last_error = str(first_error.get("detail") or "Bootstrap row apply failed.")
    else:
        chunk.status = PoolMasterDataBootstrapImportChunkStatus.SUCCEEDED
        chunk.last_error_code = ""
        chunk.last_error = ""

    chunk.finished_at = timezone.now()
    chunk.diagnostics = {"errors": errors[-100:]}
    chunk.metadata = {
        **dict(chunk.metadata or {}),
        "last_finished_at": chunk.finished_at.isoformat() if chunk.finished_at else "",
    }
    chunk.save(
        update_fields=[
            "status",
            "records_created",
            "records_updated",
            "records_skipped",
            "records_failed",
            "last_error_code",
            "last_error",
            "diagnostics",
            "metadata",
            "finished_at",
            "updated_at",
        ]
    )


def _apply_row(
    *,
    job: PoolMasterDataBootstrapImportJob,
    entity_type: str,
    row: Mapping[str, Any],
    row_index: int,
    chunk_index: int,
    resolved_ids: dict[str, set[str]],
    resolved_aliases: dict[str, dict[str, str]],
) -> BootstrapRowOutcome:
    origin_event_id = _build_origin_event_id(
        job_id=str(job.id),
        entity_type=entity_type,
        chunk_index=chunk_index,
        row_index=row_index,
        row=row,
    )
    if entity_type == PoolMasterDataBootstrapImportEntityType.PARTY:
        return _apply_party_row(
            tenant=job.tenant,
            row=row,
            origin_event_id=origin_event_id,
            job_id=str(job.id),
        )
    if entity_type == PoolMasterDataBootstrapImportEntityType.ITEM:
        return _apply_item_row(
            tenant=job.tenant,
            row=row,
            origin_event_id=origin_event_id,
            job_id=str(job.id),
        )
    if entity_type == PoolMasterDataBootstrapImportEntityType.TAX_PROFILE:
        return _apply_tax_profile_row(
            tenant=job.tenant,
            row=row,
            origin_event_id=origin_event_id,
            job_id=str(job.id),
        )
    if entity_type == PoolMasterDataBootstrapImportEntityType.GL_ACCOUNT:
        return _apply_gl_account_row(
            tenant=job.tenant,
            database=job.database,
            row=row,
            origin_event_id=origin_event_id,
            job_id=str(job.id),
        )
    if entity_type == PoolMasterDataBootstrapImportEntityType.CONTRACT:
        return _apply_contract_row(
            tenant=job.tenant,
            row=row,
            resolved_party_ids=resolved_ids[PoolMasterDataBootstrapImportEntityType.PARTY],
            resolved_party_aliases=resolved_aliases[PoolMasterDataBootstrapImportEntityType.PARTY],
            origin_event_id=origin_event_id,
            job_id=str(job.id),
        )
    if entity_type == PoolMasterDataBootstrapImportEntityType.BINDING:
        return _apply_binding_row(
            tenant=job.tenant,
            database=job.database,
            row=row,
            resolved_ids=resolved_ids,
            resolved_aliases=resolved_aliases,
            origin_event_id=origin_event_id,
            job_id=str(job.id),
        )
    return BootstrapRowOutcome(
        action="failed",
        error_code=BOOTSTRAP_IMPORT_ROW_INVALID,
        detail=f"Unsupported bootstrap entity type '{entity_type}'.",
    )


def _apply_party_row(
    *,
    tenant: Tenant,
    row: Mapping[str, Any],
    origin_event_id: str,
    job_id: str,
) -> BootstrapRowOutcome:
    canonical_id = _read_required_token(row, "canonical_id")
    if not canonical_id:
        return BootstrapRowOutcome(
            action="failed",
            error_code=BOOTSTRAP_IMPORT_ROW_REQUIRED_FIELD,
            detail="Party row requires canonical_id.",
        )
    name = _read_required_token(row, "name")
    if not name:
        return BootstrapRowOutcome(
            action="failed",
            error_code=BOOTSTRAP_IMPORT_ROW_REQUIRED_FIELD,
            detail=f"Party '{canonical_id}' requires name.",
        )

    payload = {
        "name": name,
        "full_name": _read_token(row, "full_name"),
        "inn": _read_token(row, "inn"),
        "kpp": _read_token(row, "kpp"),
        "is_our_organization": _to_bool(row.get("is_our_organization"), default=False),
        "is_counterparty": _to_bool(row.get("is_counterparty"), default=True),
        "metadata": _merge_row_metadata(row=row, job_id=job_id, origin_event_id=origin_event_id),
    }
    try:
        result = ingest_pool_master_data_source_record(
            tenant_id=str(tenant.id),
            entity_type=PoolMasterDataEntityType.PARTY,
            source_database=None,
            source_ref=_read_source_ref(row=row, fallback=canonical_id),
            source_canonical_id=canonical_id,
            canonical_payload=payload,
            origin_kind="bootstrap_import",
            origin_ref=str(job_id),
            origin_event_id=origin_event_id,
            metadata={"bootstrap_job_id": str(job_id)},
        )
    except (MasterDataCanonicalUpsertError, DjangoValidationError, IntegrityError, ValueError) as exc:
        error_code, detail = _resolve_canonical_upsert_error(exc)
        return BootstrapRowOutcome(
            action="failed",
            source_canonical_id=canonical_id,
            error_code=error_code,
            detail=detail,
        )
    except MasterDataDedupeReviewRequiredError as exc:
        return BootstrapRowOutcome(
            action="failed",
            canonical_id=str(exc.canonical_id or ""),
            source_canonical_id=canonical_id,
            error_code=exc.code,
            detail=exc.detail,
            review_item_id=str(exc.review_item_id or ""),
        )

    return BootstrapRowOutcome(
        action=str(result.action),
        canonical_id=str(result.canonical_id or ""),
        source_canonical_id=canonical_id,
        error_code=MASTER_DATA_DEDUPE_REVIEW_REQUIRED if result.blocked else "",
        detail=str(result.detail or ""),
        review_item_id=str(result.review_item.id) if result.review_item is not None else "",
    )


def _apply_item_row(
    *,
    tenant: Tenant,
    row: Mapping[str, Any],
    origin_event_id: str,
    job_id: str,
) -> BootstrapRowOutcome:
    canonical_id = _read_required_token(row, "canonical_id")
    if not canonical_id:
        return BootstrapRowOutcome(
            action="failed",
            error_code=BOOTSTRAP_IMPORT_ROW_REQUIRED_FIELD,
            detail="Item row requires canonical_id.",
        )
    name = _read_required_token(row, "name")
    if not name:
        return BootstrapRowOutcome(
            action="failed",
            error_code=BOOTSTRAP_IMPORT_ROW_REQUIRED_FIELD,
            detail=f"Item '{canonical_id}' requires name.",
        )

    payload = {
        "name": name,
        "sku": _read_token(row, "sku"),
        "unit": _read_token(row, "unit"),
        "metadata": _merge_row_metadata(row=row, job_id=job_id, origin_event_id=origin_event_id),
    }
    try:
        result = ingest_pool_master_data_source_record(
            tenant_id=str(tenant.id),
            entity_type=PoolMasterDataEntityType.ITEM,
            source_database=None,
            source_ref=_read_source_ref(row=row, fallback=canonical_id),
            source_canonical_id=canonical_id,
            canonical_payload=payload,
            origin_kind="bootstrap_import",
            origin_ref=str(job_id),
            origin_event_id=origin_event_id,
            metadata={"bootstrap_job_id": str(job_id)},
        )
    except (MasterDataCanonicalUpsertError, DjangoValidationError, IntegrityError, ValueError) as exc:
        error_code, detail = _resolve_canonical_upsert_error(exc)
        return BootstrapRowOutcome(
            action="failed",
            source_canonical_id=canonical_id,
            error_code=error_code,
            detail=detail,
        )
    except MasterDataDedupeReviewRequiredError as exc:
        return BootstrapRowOutcome(
            action="failed",
            canonical_id=str(exc.canonical_id or ""),
            source_canonical_id=canonical_id,
            error_code=exc.code,
            detail=exc.detail,
            review_item_id=str(exc.review_item_id or ""),
        )

    return BootstrapRowOutcome(
        action=str(result.action),
        canonical_id=str(result.canonical_id or ""),
        source_canonical_id=canonical_id,
        error_code=MASTER_DATA_DEDUPE_REVIEW_REQUIRED if result.blocked else "",
        detail=str(result.detail or ""),
        review_item_id=str(result.review_item.id) if result.review_item is not None else "",
    )


def _apply_tax_profile_row(
    *,
    tenant: Tenant,
    row: Mapping[str, Any],
    origin_event_id: str,
    job_id: str,
) -> BootstrapRowOutcome:
    canonical_id = _read_required_token(row, "canonical_id")
    if not canonical_id:
        return BootstrapRowOutcome(
            action="failed",
            error_code=BOOTSTRAP_IMPORT_ROW_REQUIRED_FIELD,
            detail="Tax profile row requires canonical_id.",
        )
    vat_code = _read_required_token(row, "vat_code")
    if not vat_code:
        return BootstrapRowOutcome(
            action="failed",
            error_code=BOOTSTRAP_IMPORT_ROW_REQUIRED_FIELD,
            detail=f"Tax profile '{canonical_id}' requires vat_code.",
        )

    vat_rate_raw = row.get("vat_rate")
    vat_rate = _to_decimal(vat_rate_raw, default=Decimal("0"))
    payload = {
        "vat_rate": vat_rate,
        "vat_included": _to_bool(row.get("vat_included"), default=True),
        "vat_code": vat_code,
        "metadata": _merge_row_metadata(row=row, job_id=job_id, origin_event_id=origin_event_id),
    }
    try:
        result = ingest_pool_master_data_source_record(
            tenant_id=str(tenant.id),
            entity_type=PoolMasterDataEntityType.TAX_PROFILE,
            source_database=None,
            source_ref=_read_source_ref(row=row, fallback=canonical_id),
            source_canonical_id=canonical_id,
            canonical_payload=payload,
            origin_kind="bootstrap_import",
            origin_ref=str(job_id),
            origin_event_id=origin_event_id,
            metadata={"bootstrap_job_id": str(job_id)},
        )
    except (MasterDataCanonicalUpsertError, DjangoValidationError, IntegrityError, ValueError) as exc:
        error_code, detail = _resolve_canonical_upsert_error(exc)
        return BootstrapRowOutcome(
            action="failed",
            source_canonical_id=canonical_id,
            error_code=error_code,
            detail=detail,
        )
    except MasterDataDedupeReviewRequiredError as exc:
        return BootstrapRowOutcome(
            action="failed",
            canonical_id=str(exc.canonical_id or ""),
            source_canonical_id=canonical_id,
            error_code=exc.code,
            detail=exc.detail,
            review_item_id=str(exc.review_item_id or ""),
        )

    return BootstrapRowOutcome(
        action=str(result.action),
        canonical_id=str(result.canonical_id or ""),
        source_canonical_id=canonical_id,
        error_code=MASTER_DATA_DEDUPE_REVIEW_REQUIRED if result.blocked else "",
        detail=str(result.detail or ""),
        review_item_id=str(result.review_item.id) if result.review_item is not None else "",
    )


def _apply_gl_account_row(
    *,
    tenant: Tenant,
    database: Database,
    row: Mapping[str, Any],
    origin_event_id: str,
    job_id: str,
) -> BootstrapRowOutcome:
    canonical_id = _read_required_token(row, "canonical_id")
    if not canonical_id:
        return BootstrapRowOutcome(
            action="failed",
            error_code=BOOTSTRAP_IMPORT_ROW_REQUIRED_FIELD,
            detail="GLAccount row requires canonical_id.",
        )
    code = _read_required_token(row, "code")
    if not code:
        return BootstrapRowOutcome(
            action="failed",
            error_code=BOOTSTRAP_IMPORT_ROW_REQUIRED_FIELD,
            detail=f"GLAccount '{canonical_id}' requires code.",
        )
    name = _read_required_token(row, "name")
    if not name:
        return BootstrapRowOutcome(
            action="failed",
            error_code=BOOTSTRAP_IMPORT_ROW_REQUIRED_FIELD,
            detail=f"GLAccount '{canonical_id}' requires name.",
        )
    chart_identity = _read_required_token(row, "chart_identity")
    if not chart_identity:
        return BootstrapRowOutcome(
            action="failed",
            error_code=BOOTSTRAP_IMPORT_ROW_REQUIRED_FIELD,
            detail=f"GLAccount '{canonical_id}' requires chart_identity.",
        )

    profile = get_business_configuration_profile(database=database) or {}
    config_name = _read_token(row, "config_name") or str(profile.get("config_name") or "").strip()
    config_version = _read_token(row, "config_version") or str(profile.get("config_version") or "").strip()
    if not config_name or not config_version:
        return BootstrapRowOutcome(
            action="failed",
            error_code=BOOTSTRAP_IMPORT_ROW_REQUIRED_FIELD,
            detail=(
                f"GLAccount '{canonical_id}' requires config_name and config_version "
                "from row mapping or database business configuration profile."
            ),
        )

    metadata = _merge_row_metadata(row=row, job_id=job_id, origin_event_id=origin_event_id)
    try:
        result = ingest_pool_master_data_source_record(
            tenant_id=str(tenant.id),
            entity_type=PoolMasterDataEntityType.GL_ACCOUNT,
            source_database=database,
            source_ref=_read_source_ref(row=row, fallback=canonical_id),
            source_canonical_id=canonical_id,
            canonical_payload={
                "code": code,
                "name": name,
                "chart_identity": chart_identity,
                "config_name": config_name,
                "config_version": config_version,
                "metadata": metadata,
            },
            origin_kind="bootstrap_import",
            origin_ref=str(job_id),
            origin_event_id=origin_event_id,
            metadata={"bootstrap_job_id": str(job_id), "database_id": str(database.id)},
        )
    except (MasterDataCanonicalUpsertError, DjangoValidationError, IntegrityError, ValueError) as exc:
        error_code, detail = _resolve_canonical_upsert_error(exc)
        return BootstrapRowOutcome(
            action="failed",
            source_canonical_id=canonical_id,
            error_code=error_code,
            detail=detail,
        )
    except MasterDataDedupeReviewRequiredError as exc:
        return BootstrapRowOutcome(
            action="failed",
            canonical_id=str(exc.canonical_id or ""),
            source_canonical_id=canonical_id,
            error_code=exc.code,
            detail=exc.detail,
            review_item_id=str(exc.review_item_id or ""),
        )

    return BootstrapRowOutcome(
        action=str(result.action),
        canonical_id=str(result.canonical_id or ""),
        source_canonical_id=canonical_id,
        error_code=MASTER_DATA_DEDUPE_REVIEW_REQUIRED if result.blocked else "",
        detail=str(result.detail or ""),
        review_item_id=str(result.review_item.id) if result.review_item is not None else "",
    )


def _apply_contract_row(
    *,
    tenant: Tenant,
    row: Mapping[str, Any],
    resolved_party_ids: set[str],
    resolved_party_aliases: dict[str, str],
    origin_event_id: str,
    job_id: str,
) -> BootstrapRowOutcome:
    canonical_id = _read_required_token(row, "canonical_id")
    if not canonical_id:
        return BootstrapRowOutcome(
            action="failed",
            error_code=BOOTSTRAP_IMPORT_ROW_REQUIRED_FIELD,
            detail="Contract row requires canonical_id.",
        )
    name = _read_required_token(row, "name")
    if not name:
        return BootstrapRowOutcome(
            action="failed",
            error_code=BOOTSTRAP_IMPORT_ROW_REQUIRED_FIELD,
            detail=f"Contract '{canonical_id}' requires name.",
        )
    owner_counterparty_source_id = _read_required_token(row, "owner_counterparty_canonical_id")
    owner_counterparty_canonical_id = str(
        resolved_party_aliases.get(owner_counterparty_source_id, owner_counterparty_source_id)
    ).strip()
    decision = evaluate_contract_dependency(
        owner_counterparty_canonical_id=owner_counterparty_canonical_id,
        resolved_party_canonical_ids=resolved_party_ids,
        allow_deferred=True,
    )
    if decision.decision == BOOTSTRAP_DEPENDENCY_DECISION_DEFERRED:
        return BootstrapRowOutcome(
            action="deferred",
            error_code=str(decision.error_code),
            detail=str(decision.detail),
        )
    if decision.decision == BOOTSTRAP_DEPENDENCY_DECISION_FAILED:
        return BootstrapRowOutcome(
            action="failed",
            error_code=str(decision.error_code),
            detail=str(decision.detail),
        )

    owner_counterparty = PoolMasterParty.objects.filter(
        tenant=tenant,
        canonical_id=owner_counterparty_canonical_id,
    ).first()
    if owner_counterparty is None:
        return BootstrapRowOutcome(
            action="deferred",
            error_code=BOOTSTRAP_IMPORT_CONTRACT_OWNER_NOT_FOUND,
            detail=f"Owner counterparty '{owner_counterparty_canonical_id}' is not available.",
        )

    raw_date = row.get("date")
    normalized_date = _to_date(raw_date)
    payload = {
        "name": name,
        "owner_counterparty_canonical_id": str(owner_counterparty.canonical_id),
        "number": _read_token(row, "number"),
        "date": normalized_date,
        "metadata": _merge_row_metadata(row=row, job_id=job_id, origin_event_id=origin_event_id),
    }
    try:
        result = ingest_pool_master_data_source_record(
            tenant_id=str(tenant.id),
            entity_type=PoolMasterDataEntityType.CONTRACT,
            source_database=None,
            source_ref=_read_source_ref(row=row, fallback=canonical_id),
            source_canonical_id=canonical_id,
            canonical_payload=payload,
            origin_kind="bootstrap_import",
            origin_ref=str(job_id),
            origin_event_id=origin_event_id,
            metadata={"bootstrap_job_id": str(job_id)},
        )
    except (MasterDataCanonicalUpsertError, DjangoValidationError, IntegrityError, ValueError) as exc:
        error_code, detail = _resolve_canonical_upsert_error(exc)
        return BootstrapRowOutcome(
            action="failed",
            source_canonical_id=canonical_id,
            error_code=error_code,
            detail=detail,
        )
    except MasterDataDedupeReviewRequiredError as exc:
        return BootstrapRowOutcome(
            action="failed",
            canonical_id=str(exc.canonical_id or ""),
            source_canonical_id=canonical_id,
            error_code=exc.code,
            detail=exc.detail,
            review_item_id=str(exc.review_item_id or ""),
        )

    return BootstrapRowOutcome(
        action=str(result.action),
        canonical_id=str(result.canonical_id or ""),
        source_canonical_id=canonical_id,
        error_code=MASTER_DATA_DEDUPE_REVIEW_REQUIRED if result.blocked else "",
        detail=str(result.detail or ""),
        review_item_id=str(result.review_item.id) if result.review_item is not None else "",
    )


def _apply_binding_row(
    *,
    tenant: Tenant,
    database: Database,
    row: Mapping[str, Any],
    resolved_ids: dict[str, set[str]],
    resolved_aliases: dict[str, dict[str, str]],
    origin_event_id: str,
    job_id: str,
) -> BootstrapRowOutcome:
    target_entity_type = _read_required_token(row, "entity_type")
    source_canonical_id = _read_required_token(row, "canonical_id")
    if not target_entity_type or not source_canonical_id:
        return BootstrapRowOutcome(
            action="failed",
            error_code=BOOTSTRAP_IMPORT_ROW_REQUIRED_FIELD,
            detail="Binding row requires entity_type and canonical_id.",
        )

    try:
        target_entity_type = normalize_pool_master_data_entity_type(target_entity_type)
    except ValueError:
        return BootstrapRowOutcome(
            action="failed",
            error_code=BOOTSTRAP_IMPORT_BINDING_TARGET_INVALID,
            detail=f"Unsupported binding target entity_type '{target_entity_type}'.",
        )

    canonical_id = str(
        resolved_aliases.get(target_entity_type, {}).get(source_canonical_id, source_canonical_id)
    ).strip()
    decision = evaluate_binding_dependency(
        target_entity_type=target_entity_type,
        canonical_id=canonical_id,
        resolved_canonical_ids_by_entity=resolved_ids,
        allow_deferred=True,
    )
    if decision.decision == BOOTSTRAP_DEPENDENCY_DECISION_DEFERRED:
        return BootstrapRowOutcome(
            action="deferred",
            error_code=str(decision.error_code),
            detail=str(decision.detail),
        )
    if decision.decision == BOOTSTRAP_DEPENDENCY_DECISION_FAILED:
        return BootstrapRowOutcome(
            action="failed",
            error_code=str(decision.error_code),
            detail=str(decision.detail),
        )

    ib_ref_key = _read_required_token(row, "ib_ref_key")
    if not ib_ref_key:
        return BootstrapRowOutcome(
            action="failed",
            error_code=BOOTSTRAP_IMPORT_BINDING_REF_REQUIRED,
            detail="Binding row requires ib_ref_key.",
        )

    ib_catalog_kind = _read_token(row, "ib_catalog_kind")
    owner_counterparty_source_id = _read_token(row, "owner_counterparty_canonical_id")
    owner_counterparty_canonical_id = str(
        resolved_aliases.get(PoolMasterDataBootstrapImportEntityType.PARTY, {}).get(
            owner_counterparty_source_id,
            owner_counterparty_source_id,
        )
    ).strip()
    chart_identity = _read_token(row, "chart_identity")
    binding_metadata = _merge_row_metadata(row=row, job_id=job_id, origin_event_id=origin_event_id)
    result = upsert_pool_master_data_binding(
        tenant=tenant,
        entity_type=target_entity_type,
        canonical_id=canonical_id,
        database=database,
        ib_ref_key=ib_ref_key,
        ib_catalog_kind=ib_catalog_kind,
        owner_counterparty_canonical_id=owner_counterparty_canonical_id,
        chart_identity=chart_identity,
        sync_status=PoolMasterBindingSyncStatus.UPSERTED,
        metadata=binding_metadata,
        origin_system="ib",
        origin_event_id=origin_event_id,
    )
    if result.created:
        return BootstrapRowOutcome(
            action="created",
            canonical_id=canonical_id,
            source_canonical_id=source_canonical_id,
        )
    if result.changed:
        return BootstrapRowOutcome(
            action="updated",
            canonical_id=canonical_id,
            source_canonical_id=source_canonical_id,
        )
    return BootstrapRowOutcome(
        action="skipped",
        canonical_id=canonical_id,
        source_canonical_id=source_canonical_id,
    )


def _load_resolved_canonical_ids(job: PoolMasterDataBootstrapImportJob) -> dict[str, set[str]]:
    resolved: dict[str, set[str]] = {
        PoolMasterDataBootstrapImportEntityType.PARTY: set(
            PoolMasterParty.objects.filter(tenant=job.tenant).values_list("canonical_id", flat=True)
        ),
        PoolMasterDataBootstrapImportEntityType.ITEM: set(
            PoolMasterItem.objects.filter(tenant=job.tenant).values_list("canonical_id", flat=True)
        ),
        PoolMasterDataBootstrapImportEntityType.TAX_PROFILE: set(
            PoolMasterTaxProfile.objects.filter(tenant=job.tenant).values_list("canonical_id", flat=True)
        ),
        PoolMasterDataBootstrapImportEntityType.GL_ACCOUNT: set(
            PoolMasterGLAccount.objects.filter(tenant=job.tenant).values_list("canonical_id", flat=True)
        ),
        PoolMasterDataBootstrapImportEntityType.CONTRACT: set(
            PoolMasterContract.objects.filter(tenant=job.tenant).values_list("canonical_id", flat=True)
        ),
        PoolMasterDataBootstrapImportEntityType.BINDING: set(),
    }
    return {key: {str(value or "").strip() for value in values} for key, values in resolved.items()}


def _load_resolved_canonical_aliases() -> dict[str, dict[str, str]]:
    return {
        PoolMasterDataBootstrapImportEntityType.PARTY: {},
        PoolMasterDataBootstrapImportEntityType.ITEM: {},
        PoolMasterDataBootstrapImportEntityType.TAX_PROFILE: {},
        PoolMasterDataBootstrapImportEntityType.GL_ACCOUNT: {},
        PoolMasterDataBootstrapImportEntityType.CONTRACT: {},
        PoolMasterDataBootstrapImportEntityType.BINDING: {},
    }


def _mark_resolved_id(
    *,
    resolved_ids: dict[str, set[str]],
    entity_type: str,
    canonical_id: str,
) -> None:
    normalized_entity = str(entity_type or "").strip()
    normalized_id = str(canonical_id or "").strip()
    if not normalized_id:
        return
    resolved_ids.setdefault(normalized_entity, set()).add(normalized_id)


def _mark_resolved_alias(
    *,
    resolved_aliases: dict[str, dict[str, str]],
    entity_type: str,
    source_canonical_id: str,
    canonical_id: str,
) -> None:
    normalized_entity = str(entity_type or "").strip()
    normalized_source_id = str(source_canonical_id or "").strip()
    normalized_canonical_id = str(canonical_id or "").strip()
    if not normalized_source_id or not normalized_canonical_id:
        return
    resolved_aliases.setdefault(normalized_entity, {})[normalized_source_id] = normalized_canonical_id


def _raise_if_job_canceled(*, job_id: str) -> None:
    status = (
        PoolMasterDataBootstrapImportJob.objects.filter(id=str(job_id)).values_list("status", flat=True).first()
    )
    if status == PoolMasterDataBootstrapImportJobStatus.CANCELED:
        raise _BootstrapExecutionCanceled("Bootstrap import canceled by operator.")


def _mark_chunk_canceled(*, chunk: PoolMasterDataBootstrapImportChunk) -> None:
    now = timezone.now()
    chunk.status = PoolMasterDataBootstrapImportChunkStatus.CANCELED
    chunk.last_error_code = BOOTSTRAP_IMPORT_CANCELED
    chunk.last_error = "Chunk canceled by operator."
    chunk.finished_at = now
    diagnostics = dict(chunk.diagnostics or {})
    errors = list(diagnostics.get("errors") or [])
    errors.append(
        {
            "code": BOOTSTRAP_IMPORT_CANCELED,
            "detail": "Chunk canceled by operator.",
            "at": now.isoformat(),
        }
    )
    diagnostics["errors"] = errors[-100:]
    chunk.diagnostics = sanitize_master_data_sync_value(diagnostics)
    chunk.metadata = {
        **dict(chunk.metadata or {}),
        "last_finished_at": now.isoformat(),
    }
    chunk.save(
        update_fields=[
            "status",
            "last_error_code",
            "last_error",
            "diagnostics",
            "metadata",
            "finished_at",
            "updated_at",
        ]
    )


def _rebuild_report_and_progress(*, job: PoolMasterDataBootstrapImportJob) -> None:
    chunks = list(job.chunks.all())
    created_count = sum(int(chunk.records_created or 0) for chunk in chunks)
    updated_count = sum(int(chunk.records_updated or 0) for chunk in chunks)
    skipped_count = sum(int(chunk.records_skipped or 0) for chunk in chunks)
    failed_count = sum(int(chunk.records_failed or 0) for chunk in chunks)
    deferred_count = sum(
        1 for chunk in chunks if chunk.status == PoolMasterDataBootstrapImportChunkStatus.DEFERRED
    )
    diagnostics_errors: list[dict[str, Any]] = []
    for chunk in chunks:
        diagnostics = chunk.diagnostics if isinstance(chunk.diagnostics, dict) else {}
        errors = diagnostics.get("errors")
        if not isinstance(errors, list):
            continue
        for item in errors:
            if isinstance(item, Mapping):
                diagnostics_errors.append(
                    {
                        "chunk_id": str(chunk.id),
                        "entity_type": str(chunk.entity_type),
                        "chunk_index": int(chunk.chunk_index or 0),
                        **dict(item),
                    }
                )

    report, _ = PoolMasterDataBootstrapImportReport.objects.get_or_create(job=job)
    report.created_count = created_count
    report.updated_count = updated_count
    report.skipped_count = skipped_count
    report.failed_count = failed_count
    report.deferred_count = deferred_count
    report.diagnostics = {"errors": diagnostics_errors[-200:]}
    report.save(
        update_fields=[
            "created_count",
            "updated_count",
            "skipped_count",
            "failed_count",
            "deferred_count",
            "diagnostics",
            "updated_at",
        ]
    )

    total_chunks = len(chunks)
    status_counts = {
        "pending": 0,
        "running": 0,
        "succeeded": 0,
        "failed": 0,
        "deferred": 0,
        "canceled": 0,
    }
    for chunk in chunks:
        key = str(chunk.status or "").strip().lower()
        if key in status_counts:
            status_counts[key] += 1
    processed_chunks = (
        status_counts["succeeded"] + status_counts["failed"] + status_counts["deferred"] + status_counts["canceled"]
    )
    completion_ratio = (processed_chunks / total_chunks) if total_chunks > 0 else 0.0

    metadata = job.metadata if isinstance(job.metadata, dict) else {}
    metadata["progress"] = {
        "total_chunks": total_chunks,
        "processed_chunks": processed_chunks,
        "pending_chunks": status_counts["pending"],
        "running_chunks": status_counts["running"],
        "succeeded_chunks": status_counts["succeeded"],
        "failed_chunks": status_counts["failed"],
        "deferred_chunks": status_counts["deferred"],
        "canceled_chunks": status_counts["canceled"],
        "completion_ratio": round(completion_ratio, 4),
    }
    metadata["chunk_status_counts"] = status_counts
    job.metadata = metadata

    latest_error_chunk = next(
        (
            chunk
            for chunk in sorted(chunks, key=lambda item: item.updated_at, reverse=True)
            if str(chunk.last_error_code or "").strip()
        ),
        None,
    )
    if latest_error_chunk is not None:
        job.last_error_code = str(latest_error_chunk.last_error_code or "")
        job.last_error = sanitize_master_data_sync_text(str(latest_error_chunk.last_error or ""))
    elif job.status in {PoolMasterDataBootstrapImportJobStatus.FINALIZED}:
        job.last_error_code = ""
        job.last_error = ""
    job.save(update_fields=["metadata", "last_error_code", "last_error", "updated_at"])


def _fetch_rows_for_scope(
    *,
    tenant_id: str,
    database: Database,
    entity_scope: list[str],
    actor_id: str,
) -> dict[str, list[dict[str, Any]]]:
    ordered_scope = resolve_bootstrap_import_dependency_order(selected_scope=entity_scope)
    rows_by_entity: dict[str, list[dict[str, Any]]] = {}
    for entity_type in ordered_scope:
        rows_by_entity[entity_type] = fetch_pool_master_data_bootstrap_source_rows(
            tenant_id=tenant_id,
            database=database,
            entity_type=entity_type,
            actor_id=actor_id,
        )
    return rows_by_entity


def _build_dry_run_summary(
    *,
    rows_by_entity: Mapping[str, list[dict[str, Any]]],
    chunk_size: int,
) -> dict[str, Any]:
    entities: list[dict[str, Any]] = []
    rows_total = 0
    chunks_total = 0
    for entity_type, rows in rows_by_entity.items():
        total = len(rows)
        chunk_count = len(_chunk_rows(rows=rows, chunk_size=chunk_size))
        rows_total += total
        chunks_total += chunk_count
        entities.append(
            {
                "entity_type": str(entity_type),
                "rows_total": total,
                "chunks_total": chunk_count,
            }
        )
    return {
        "rows_total": rows_total,
        "chunks_total": chunks_total,
        "entities": entities,
        "generated_at": timezone.now().isoformat(),
    }


def _chunk_rows(*, rows: list[dict[str, Any]], chunk_size: int) -> list[list[dict[str, Any]]]:
    if not rows:
        return []
    size = _safe_chunk_size(chunk_size)
    return [rows[index : index + size] for index in range(0, len(rows), size)]


def _safe_chunk_size(value: Any) -> int:
    try:
        chunk_size = int(value)
    except (TypeError, ValueError):
        return 200
    return max(1, min(chunk_size, 1000))


def _normalize_mode(mode: str) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized not in {BOOTSTRAP_IMPORT_MODE_DRY_RUN, BOOTSTRAP_IMPORT_MODE_EXECUTE}:
        raise ValueError(f"{BOOTSTRAP_IMPORT_MODE_INVALID}: unsupported mode '{mode}'")
    return normalized


def _normalize_entity_scope(entity_scope: Iterable[str]) -> list[str]:
    selected = list(entity_scope or [])
    if not selected:
        raise ValueError(f"{BOOTSTRAP_IMPORT_SCOPE_EMPTY}: entity_scope must not be empty")
    ordered_scope = resolve_bootstrap_import_dependency_order(selected_scope=selected)
    return list(ordered_scope)


def _get_job_or_raise(*, tenant_id: str, job_id: str) -> PoolMasterDataBootstrapImportJob:
    job = (
        PoolMasterDataBootstrapImportJob.objects.filter(
            id=str(job_id or "").strip(),
            tenant_id=str(tenant_id or "").strip(),
        )
        .select_related("database", "report", "tenant")
        .first()
    )
    if job is None:
        raise LookupError(f"{BOOTSTRAP_IMPORT_JOB_NOT_FOUND}: job '{job_id}' was not found")
    return job


def _refresh_job(*, job_id: str) -> PoolMasterDataBootstrapImportJob:
    return (
        PoolMasterDataBootstrapImportJob.objects.select_related("database", "report", "tenant")
        .prefetch_related("chunks")
        .get(id=str(job_id))
    )


def _append_job_audit(
    *,
    job: PoolMasterDataBootstrapImportJob,
    action: str,
    actor_id: str,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    payload = sanitize_master_data_sync_value(dict(metadata or {}))
    job_metadata = job.metadata if isinstance(job.metadata, dict) else {}
    history = job_metadata.get("audit_trail")
    events = list(history) if isinstance(history, list) else []
    events.append(
        {
            "action": str(action or "").strip(),
            "actor_id": str(actor_id or "").strip(),
            "at": timezone.now().isoformat(),
            "metadata": payload,
        }
    )
    job_metadata["audit_trail"] = events[-200:]
    job.metadata = job_metadata


def _merge_row_metadata(
    *,
    row: Mapping[str, Any],
    job_id: str,
    origin_event_id: str,
) -> dict[str, Any]:
    raw_metadata = row.get("metadata")
    metadata = dict(raw_metadata) if isinstance(raw_metadata, Mapping) else {}
    metadata["sync_origin"] = {
        "origin_system": "ib",
        "origin_event_id": origin_event_id,
    }
    metadata["bootstrap_import"] = {
        "job_id": str(job_id),
        "origin_event_id": origin_event_id,
    }
    return sanitize_master_data_sync_value(metadata)


def _serialize_chunk(chunk: PoolMasterDataBootstrapImportChunk) -> dict[str, Any]:
    diagnostics = chunk.diagnostics if isinstance(chunk.diagnostics, dict) else {}
    metadata = chunk.metadata if isinstance(chunk.metadata, dict) else {}
    return {
        "id": str(chunk.id),
        "job_id": str(chunk.job_id),
        "entity_type": str(chunk.entity_type),
        "chunk_index": int(chunk.chunk_index),
        "status": str(chunk.status),
        "attempt_count": int(chunk.attempt_count or 0),
        "idempotency_key": str(chunk.idempotency_key or ""),
        "records_total": int(chunk.records_total or 0),
        "records_created": int(chunk.records_created or 0),
        "records_updated": int(chunk.records_updated or 0),
        "records_skipped": int(chunk.records_skipped or 0),
        "records_failed": int(chunk.records_failed or 0),
        "last_error_code": str(chunk.last_error_code or ""),
        "last_error": sanitize_master_data_sync_text(str(chunk.last_error or "")),
        "diagnostics": sanitize_master_data_sync_value(diagnostics),
        "metadata": sanitize_master_data_sync_value(metadata),
        "started_at": chunk.started_at,
        "finished_at": chunk.finished_at,
        "created_at": chunk.created_at,
        "updated_at": chunk.updated_at,
    }


def _resolve_canonical_upsert_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, MasterDataCanonicalUpsertError):
        return (
            str(exc.code or BOOTSTRAP_IMPORT_ROW_INVALID),
            sanitize_master_data_sync_text(str(exc.detail or "Canonical upsert failed.")),
        )
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "message_dict"):
            return (
                BOOTSTRAP_IMPORT_ROW_INVALID,
                sanitize_master_data_sync_text(str(exc.message_dict)),
            )
        return (
            BOOTSTRAP_IMPORT_ROW_INVALID,
            sanitize_master_data_sync_text(str(exc)),
        )

    detail = sanitize_master_data_sync_text(str(exc) or "Bootstrap row apply failed.")
    if ":" in detail:
        code_candidate, detail_candidate = detail.split(":", 1)
        normalized_code = str(code_candidate or "").strip()
        if (
            normalized_code
            and normalized_code.upper() == normalized_code
            and len(normalized_code) <= 128
        ):
            resolved_detail = sanitize_master_data_sync_text(
                str(detail_candidate or "").strip() or detail
            )
            return normalized_code, resolved_detail
    return BOOTSTRAP_IMPORT_ROW_INVALID, detail


def _read_token(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    return str(value or "").strip()


def _read_source_ref(*, row: Mapping[str, Any], fallback: str) -> str:
    candidate = _read_token(row, "source_ref") or _read_token(row, "ib_ref_key") or str(fallback or "").strip()
    return candidate


def _read_required_token(row: Mapping[str, Any], key: str) -> str:
    return _read_token(row, key)


def _to_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"1", "true", "yes", "on"}:
            return True
        if token in {"0", "false", "no", "off"}:
            return False
    return bool(default)


def _to_decimal(value: Any, *, default: Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def _to_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    token = str(value or "").strip()
    if not token:
        return None
    try:
        return date.fromisoformat(token[:10])
    except ValueError:
        return None


def _build_origin_event_id(
    *,
    job_id: str,
    entity_type: str,
    chunk_index: int,
    row_index: int,
    row: Mapping[str, Any],
) -> str:
    canonical_id = str(row.get("canonical_id") or "").strip()
    digest_source = "|".join(
        [
            str(job_id or "").strip(),
            str(entity_type or "").strip(),
            str(chunk_index),
            str(row_index),
            canonical_id,
        ]
    )
    digest = sha256(digest_source.encode("utf-8")).hexdigest()[:20]
    return f"bootstrap:{digest}"


def _default_progress() -> dict[str, Any]:
    return {
        "total_chunks": 0,
        "processed_chunks": 0,
        "pending_chunks": 0,
        "running_chunks": 0,
        "succeeded_chunks": 0,
        "failed_chunks": 0,
        "deferred_chunks": 0,
        "canceled_chunks": 0,
        "completion_ratio": 0.0,
    }


def _as_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return sanitize_master_data_sync_value(dict(value))


def _as_list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    return sanitize_master_data_sync_value(list(value))


__all__ = [
    "BOOTSTRAP_IMPORT_ASYNC_EXECUTOR_UNAVAILABLE",
    "BOOTSTRAP_IMPORT_DATABASE_TENANT_MISMATCH",
    "BOOTSTRAP_IMPORT_JOB_NOT_FOUND",
    "BOOTSTRAP_IMPORT_MODE_DRY_RUN",
    "BOOTSTRAP_IMPORT_MODE_EXECUTE",
    "BOOTSTRAP_IMPORT_MODE_INVALID",
    "BOOTSTRAP_IMPORT_PREFLIGHT_FAILED",
    "BOOTSTRAP_IMPORT_SCOPE_EMPTY",
    "BootstrapImportPreflightBlockedError",
    "cancel_pool_master_data_bootstrap_import_job",
    "create_pool_master_data_bootstrap_import_job",
    "get_pool_master_data_bootstrap_import_job",
    "list_pool_master_data_bootstrap_import_jobs",
    "run_pool_master_data_bootstrap_import_job_execution",
    "run_pool_master_data_bootstrap_dry_run_preview",
    "retry_failed_pool_master_data_bootstrap_import_chunks",
    "run_pool_master_data_bootstrap_preflight_preview",
    "serialize_pool_master_data_bootstrap_import_job",
]
