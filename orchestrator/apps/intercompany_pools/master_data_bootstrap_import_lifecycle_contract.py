from __future__ import annotations

from .models import PoolMasterDataBootstrapImportJobStatus


POOL_MASTER_DATA_BOOTSTRAP_IMPORT_LIFECYCLE_CONTRACT = "pool_master_data_bootstrap_import_lifecycle.v1"

POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_PREFLIGHT = "preflight"
POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_DRY_RUN = "dry_run"
POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_EXECUTE = "execute"
POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_FINALIZE = "finalize"

POOL_MASTER_DATA_BOOTSTRAP_UNKNOWN_STEP = "POOL_MASTER_DATA_BOOTSTRAP_UNKNOWN_STEP"
POOL_MASTER_DATA_BOOTSTRAP_UNKNOWN_STATUS = "POOL_MASTER_DATA_BOOTSTRAP_UNKNOWN_STATUS"
POOL_MASTER_DATA_BOOTSTRAP_PREFLIGHT_BLOCKED = "POOL_MASTER_DATA_BOOTSTRAP_PREFLIGHT_BLOCKED"
POOL_MASTER_DATA_BOOTSTRAP_DRY_RUN_BLOCKED = "POOL_MASTER_DATA_BOOTSTRAP_DRY_RUN_BLOCKED"
POOL_MASTER_DATA_BOOTSTRAP_EXECUTE_BLOCKED = "POOL_MASTER_DATA_BOOTSTRAP_EXECUTE_BLOCKED"
POOL_MASTER_DATA_BOOTSTRAP_FINALIZE_BLOCKED = "POOL_MASTER_DATA_BOOTSTRAP_FINALIZE_BLOCKED"
POOL_MASTER_DATA_BOOTSTRAP_FAIL_CLOSED_ERROR_CODE_INVALID = (
    "POOL_MASTER_DATA_BOOTSTRAP_FAIL_CLOSED_ERROR_CODE_INVALID"
)

_ALLOWED_STATUSES_BY_STEP = {
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_PREFLIGHT: {
        PoolMasterDataBootstrapImportJobStatus.PREFLIGHT_PENDING,
        PoolMasterDataBootstrapImportJobStatus.PREFLIGHT_FAILED,
    },
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_DRY_RUN: {
        PoolMasterDataBootstrapImportJobStatus.DRY_RUN_PENDING,
        PoolMasterDataBootstrapImportJobStatus.DRY_RUN_FAILED,
    },
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_EXECUTE: {
        PoolMasterDataBootstrapImportJobStatus.EXECUTE_PENDING,
    },
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_FINALIZE: {
        PoolMasterDataBootstrapImportJobStatus.RUNNING,
    },
}

_BLOCKED_ERROR_BY_STEP = {
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_PREFLIGHT: POOL_MASTER_DATA_BOOTSTRAP_PREFLIGHT_BLOCKED,
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_DRY_RUN: POOL_MASTER_DATA_BOOTSTRAP_DRY_RUN_BLOCKED,
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_EXECUTE: POOL_MASTER_DATA_BOOTSTRAP_EXECUTE_BLOCKED,
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_FINALIZE: POOL_MASTER_DATA_BOOTSTRAP_FINALIZE_BLOCKED,
}

_SUCCESS_STATUS_BY_STEP = {
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_PREFLIGHT: PoolMasterDataBootstrapImportJobStatus.DRY_RUN_PENDING,
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_DRY_RUN: PoolMasterDataBootstrapImportJobStatus.EXECUTE_PENDING,
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_EXECUTE: PoolMasterDataBootstrapImportJobStatus.RUNNING,
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_FINALIZE: PoolMasterDataBootstrapImportJobStatus.FINALIZED,
}

_FAILURE_STATUS_BY_STEP = {
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_PREFLIGHT: PoolMasterDataBootstrapImportJobStatus.PREFLIGHT_FAILED,
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_DRY_RUN: PoolMasterDataBootstrapImportJobStatus.DRY_RUN_FAILED,
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_EXECUTE: PoolMasterDataBootstrapImportJobStatus.FAILED,
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_FINALIZE: PoolMasterDataBootstrapImportJobStatus.FAILED,
}

_FAIL_CLOSED_ERROR_CODES = frozenset(
    {
        POOL_MASTER_DATA_BOOTSTRAP_UNKNOWN_STEP,
        POOL_MASTER_DATA_BOOTSTRAP_UNKNOWN_STATUS,
        POOL_MASTER_DATA_BOOTSTRAP_PREFLIGHT_BLOCKED,
        POOL_MASTER_DATA_BOOTSTRAP_DRY_RUN_BLOCKED,
        POOL_MASTER_DATA_BOOTSTRAP_EXECUTE_BLOCKED,
        POOL_MASTER_DATA_BOOTSTRAP_FINALIZE_BLOCKED,
    }
)


def _fail(code: str, detail: str) -> ValueError:
    return ValueError(f"{code}: {detail}")


def require_bootstrap_import_fail_closed_error_code(error_code: str) -> str:
    normalized_error_code = str(error_code or "").strip().upper()
    if normalized_error_code not in _FAIL_CLOSED_ERROR_CODES:
        raise _fail(
            POOL_MASTER_DATA_BOOTSTRAP_FAIL_CLOSED_ERROR_CODE_INVALID,
            f"unsupported fail-closed error code '{error_code}'",
        )
    return normalized_error_code


def require_bootstrap_import_step_allowed(*, current_status: str, step: str) -> None:
    normalized_step = str(step or "").strip().lower()
    if normalized_step not in _ALLOWED_STATUSES_BY_STEP:
        raise _fail(
            POOL_MASTER_DATA_BOOTSTRAP_UNKNOWN_STEP,
            f"unsupported lifecycle step '{step}'",
        )

    normalized_status = str(current_status or "").strip().lower()
    if normalized_status not in set(PoolMasterDataBootstrapImportJobStatus.values):
        raise _fail(
            POOL_MASTER_DATA_BOOTSTRAP_UNKNOWN_STATUS,
            f"unsupported lifecycle status '{current_status}'",
        )

    if normalized_status not in _ALLOWED_STATUSES_BY_STEP[normalized_step]:
        raise _fail(
            _BLOCKED_ERROR_BY_STEP[normalized_step],
            f"step '{normalized_step}' is blocked for status '{normalized_status}'",
        )


def resolve_bootstrap_import_next_status(*, current_status: str, step: str, succeeded: bool) -> str:
    normalized_step = str(step or "").strip().lower()
    require_bootstrap_import_step_allowed(current_status=current_status, step=normalized_step)
    if succeeded:
        return _SUCCESS_STATUS_BY_STEP[normalized_step]
    return _FAILURE_STATUS_BY_STEP[normalized_step]
