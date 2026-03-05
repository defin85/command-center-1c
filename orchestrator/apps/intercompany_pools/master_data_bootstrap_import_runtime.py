from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging

from django.db import close_old_connections


logger = logging.getLogger(__name__)

_BOOTSTRAP_IMPORT_EXECUTOR = ThreadPoolExecutor(max_workers=4)


def _execute_bootstrap_import_job_in_background(
    *,
    job_id: str,
    actor_id: str,
    retry_failed_only: bool,
) -> None:
    close_old_connections()
    try:
        from .master_data_bootstrap_import_service import (
            run_pool_master_data_bootstrap_import_job_execution,
        )

        run_pool_master_data_bootstrap_import_job_execution(
            job_id=job_id,
            actor_id=actor_id,
            retry_failed_only=retry_failed_only,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Bootstrap import background execution failed",
            extra={
                "job_id": str(job_id),
                "retry_failed_only": bool(retry_failed_only),
                "error": str(exc),
            },
        )
    finally:
        close_old_connections()


def start_pool_master_data_bootstrap_import_job_execution(
    *,
    job_id: str,
    actor_id: str,
    retry_failed_only: bool,
) -> bool:
    try:
        _BOOTSTRAP_IMPORT_EXECUTOR.submit(
            _execute_bootstrap_import_job_in_background,
            job_id=str(job_id),
            actor_id=str(actor_id or ""),
            retry_failed_only=bool(retry_failed_only),
        )
        return True
    except RuntimeError as exc:
        logger.error(
            "Bootstrap import async executor unavailable",
            extra={
                "job_id": str(job_id),
                "retry_failed_only": bool(retry_failed_only),
                "error": str(exc),
            },
        )
        return False


__all__ = [
    "start_pool_master_data_bootstrap_import_job_execution",
]
