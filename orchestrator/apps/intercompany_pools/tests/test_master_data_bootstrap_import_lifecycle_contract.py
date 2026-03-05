from __future__ import annotations

import pytest

from apps.intercompany_pools.master_data_bootstrap_import_lifecycle_contract import (
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_DRY_RUN,
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_EXECUTE,
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_FINALIZE,
    POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_PREFLIGHT,
    require_bootstrap_import_fail_closed_error_code,
    resolve_bootstrap_import_next_status,
)
from apps.intercompany_pools.models import PoolMasterDataBootstrapImportJobStatus


def test_resolve_bootstrap_import_next_status_for_success_path() -> None:
    status = resolve_bootstrap_import_next_status(
        current_status=PoolMasterDataBootstrapImportJobStatus.PREFLIGHT_PENDING,
        step=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_PREFLIGHT,
        succeeded=True,
    )
    assert status == PoolMasterDataBootstrapImportJobStatus.DRY_RUN_PENDING

    status = resolve_bootstrap_import_next_status(
        current_status=status,
        step=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_DRY_RUN,
        succeeded=True,
    )
    assert status == PoolMasterDataBootstrapImportJobStatus.EXECUTE_PENDING

    status = resolve_bootstrap_import_next_status(
        current_status=status,
        step=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_EXECUTE,
        succeeded=True,
    )
    assert status == PoolMasterDataBootstrapImportJobStatus.RUNNING

    status = resolve_bootstrap_import_next_status(
        current_status=status,
        step=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_FINALIZE,
        succeeded=True,
    )
    assert status == PoolMasterDataBootstrapImportJobStatus.FINALIZED


def test_resolve_bootstrap_import_next_status_for_fail_closed_path() -> None:
    status = resolve_bootstrap_import_next_status(
        current_status=PoolMasterDataBootstrapImportJobStatus.PREFLIGHT_PENDING,
        step=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_PREFLIGHT,
        succeeded=False,
    )
    assert status == PoolMasterDataBootstrapImportJobStatus.PREFLIGHT_FAILED

    status = resolve_bootstrap_import_next_status(
        current_status=PoolMasterDataBootstrapImportJobStatus.DRY_RUN_PENDING,
        step=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_DRY_RUN,
        succeeded=False,
    )
    assert status == PoolMasterDataBootstrapImportJobStatus.DRY_RUN_FAILED

    status = resolve_bootstrap_import_next_status(
        current_status=PoolMasterDataBootstrapImportJobStatus.EXECUTE_PENDING,
        step=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_EXECUTE,
        succeeded=False,
    )
    assert status == PoolMasterDataBootstrapImportJobStatus.FAILED

    status = resolve_bootstrap_import_next_status(
        current_status=PoolMasterDataBootstrapImportJobStatus.RUNNING,
        step=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_FINALIZE,
        succeeded=False,
    )
    assert status == PoolMasterDataBootstrapImportJobStatus.FAILED


def test_resolve_bootstrap_import_next_status_blocks_invalid_step_transition() -> None:
    with pytest.raises(ValueError, match="POOL_MASTER_DATA_BOOTSTRAP_EXECUTE_BLOCKED"):
        resolve_bootstrap_import_next_status(
            current_status=PoolMasterDataBootstrapImportJobStatus.PREFLIGHT_PENDING,
            step=POOL_MASTER_DATA_BOOTSTRAP_IMPORT_STEP_EXECUTE,
            succeeded=True,
        )


def test_require_bootstrap_import_fail_closed_error_code_rejects_unknown_code() -> None:
    with pytest.raises(ValueError, match="POOL_MASTER_DATA_BOOTSTRAP_FAIL_CLOSED_ERROR_CODE_INVALID"):
        require_bootstrap_import_fail_closed_error_code("SOME_UNLISTED_ERROR")
