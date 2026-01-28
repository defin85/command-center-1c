from typing import Any, Dict

from .runtime import Task, logger


class MiscEventHandlersMixin:
    def handle_infobase_locked(self, payload: Dict[str, Any], correlation_id: str) -> None:
        cluster_id = payload.get("cluster_id")
        infobase_id = payload.get("infobase_id")
        reason = payload.get("reason")
        logger.info(
            "Infobase locked event: cluster_id=%s, infobase_id=%s, reason=%s, correlation_id=%s",
            cluster_id,
            infobase_id,
            reason,
            correlation_id,
        )
        self._update_task_status_from_correlation_id(
            correlation_id=correlation_id,
            status=Task.STATUS_COMPLETED,
            result=payload,
        )

    def handle_sessions_closed(self, payload: Dict[str, Any], correlation_id: str) -> None:
        cluster_id = payload.get("cluster_id")
        infobase_id = payload.get("infobase_id")
        sessions_closed = payload.get("sessions_closed")
        duration_seconds = payload.get("duration_seconds")
        logger.info(
            "Sessions closed event: cluster_id=%s, infobase_id=%s, sessions_closed=%s, "
            "duration_seconds=%s, correlation_id=%s",
            cluster_id,
            infobase_id,
            sessions_closed,
            duration_seconds,
            correlation_id,
        )
        self._update_task_status_from_correlation_id(
            correlation_id=correlation_id,
            status=Task.STATUS_COMPLETED,
            result=payload,
        )

