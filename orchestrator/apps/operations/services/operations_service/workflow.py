from __future__ import annotations

from datetime import datetime, timedelta, timezone as dt_timezone
import uuid
from typing import Any, Optional

from django.db import IntegrityError, transaction
from django.utils import timezone

from ...events import event_publisher, flow_publisher
from ...prometheus_metrics import set_pool_master_data_sync_queue_backlog_by_scheduling
from ...redis_client import redis_client
from .types import EnqueueResult, classify_enqueue_error_code, logger


class OperationsServiceWorkflowMixin:
    SYNC_SCHEDULING_PRIORITY_ENUM = frozenset(("p0", "p1", "p2", "p3"))
    SYNC_SCHEDULING_ROLE_ENUM = frozenset(
        ("inbound", "outbound", "read", "reconcile", "manual_remediation")
    )

    @staticmethod
    def _extract_actor_username_from_input_context(input_context: dict[str, Any] | None) -> str:
        context = input_context if isinstance(input_context, dict) else {}

        for key in ("executed_by", "created_by", "requested_by", "actor_username"):
            candidate = str(context.get(key) or "").strip()
            if candidate:
                return candidate

        publication_auth = context.get("publication_auth")
        if isinstance(publication_auth, dict):
            strategy = str(publication_auth.get("strategy") or "").strip().lower()
            actor_username = str(publication_auth.get("actor_username") or "").strip()
            if strategy == "actor" and actor_username:
                return actor_username

        return ""

    @classmethod
    def _resolve_workflow_created_by(
        cls,
        *,
        execution_id: str,
        workflow_config: Optional[dict[str, Any]] = None,
        execution: Any = None,
    ) -> str:
        config = workflow_config if isinstance(workflow_config, dict) else {}
        for key in ("created_by", "executed_by", "requested_by", "actor_username"):
            candidate = str(config.get(key) or "").strip()
            if candidate:
                return candidate

        if execution is None:
            try:
                from apps.templates.workflow.models import WorkflowExecution

                execution = WorkflowExecution.objects.only("input_context").filter(id=execution_id).first()
            except Exception:
                execution = None

        input_context = (
            execution.input_context
            if isinstance(getattr(execution, "input_context", None), dict)
            else {}
        )
        actor_username = cls._extract_actor_username_from_input_context(input_context)
        if actor_username:
            return actor_username

        return "workflow_engine"

    @staticmethod
    def _parse_rfc3339_utc_timestamp(value: Any) -> datetime | None:
        token = str(value or "").strip()
        if not token or "T" not in token:
            return None
        normalized = token[:-1] + "+00:00" if token.endswith("Z") else token
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if timezone.is_naive(parsed):
            return None
        if parsed.utcoffset() != timedelta(0):
            return None
        return parsed.astimezone(dt_timezone.utc)

    @staticmethod
    def _format_rfc3339_utc_timestamp(value: datetime) -> str:
        normalized = value.astimezone(dt_timezone.utc).replace(microsecond=0)
        return normalized.isoformat().replace("+00:00", "Z")

    @classmethod
    def _validate_workflow_scheduling_contract(
        cls,
        *,
        execution_id: str,
        workflow_config: dict[str, Any],
    ) -> tuple[dict[str, str], EnqueueResult | None]:
        config = workflow_config if isinstance(workflow_config, dict) else {}
        is_sync_workload = bool(str(config.get("sync_job_id") or "").strip())
        has_new_scheduling_fields = any(
            str(config.get(field_name) or "").strip()
            for field_name in ("role", "server_affinity", "deadline_at")
        )
        requires_scheduling_contract = is_sync_workload or has_new_scheduling_fields
        if not requires_scheduling_contract:
            return {}, None

        priority = str(config.get("priority") or "").strip().lower()
        role = str(config.get("role") or "").strip().lower()
        server_affinity = str(config.get("server_affinity") or "").strip()
        deadline_at_token = str(config.get("deadline_at") or "").strip()

        invalid_fields: list[str] = []
        if priority not in cls.SYNC_SCHEDULING_PRIORITY_ENUM:
            invalid_fields.append("priority")
        if role not in cls.SYNC_SCHEDULING_ROLE_ENUM:
            invalid_fields.append("role")
        if not server_affinity:
            invalid_fields.append("server_affinity")
        parsed_deadline_at = cls._parse_rfc3339_utc_timestamp(deadline_at_token)
        if parsed_deadline_at is None:
            invalid_fields.append("deadline_at")

        if invalid_fields:
            return {}, EnqueueResult(
                success=False,
                operation_id=execution_id,
                status="error",
                error=(
                    "Invalid scheduling contract fields: "
                    + ", ".join(sorted(set(invalid_fields)))
                    + ". Required: priority, role, server_affinity, deadline_at."
                ),
                error_code="SCHEDULING_CONTRACT_INVALID",
            )

        now_utc = timezone.now().astimezone(dt_timezone.utc)
        if parsed_deadline_at <= now_utc:
            return {}, EnqueueResult(
                success=False,
                operation_id=execution_id,
                status="error",
                error="deadline_at must be in the future (RFC3339 UTC).",
                error_code="SCHEDULING_DEADLINE_INVALID",
            )

        return {
            "priority": priority,
            "role": role,
            "server_affinity": server_affinity,
            "deadline_at": cls._format_rfc3339_utc_timestamp(parsed_deadline_at),
        }, None

    @classmethod
    def _upsert_workflow_root_operation(
        cls,
        *,
        execution_id: str,
        message_payload: dict[str, Any],
    ):
        from ...models import BatchOperation

        message = message_payload if isinstance(message_payload, dict) else {}
        payload = message.get("payload") if isinstance(message.get("payload"), dict) else {}
        execution_config = (
            message.get("execution_config") if isinstance(message.get("execution_config"), dict) else {}
        )
        message_metadata = message.get("metadata") if isinstance(message.get("metadata"), dict) else {}

        normalized_payload = {
            "data": payload.get("data") if isinstance(payload.get("data"), dict) else {},
            "filters": payload.get("filters") if isinstance(payload.get("filters"), dict) else {},
            "options": payload.get("options") if isinstance(payload.get("options"), dict) else {},
        }

        normalized_metadata = cls._build_execution_metadata(
            operation_id=execution_id,
            metadata=message_metadata,
        )
        normalized_metadata["workflow_execution_id"] = execution_id
        normalized_metadata["root_operation_id"] = execution_id

        name = f"Workflow execution {execution_id}"
        description = "Root workflow execution projection"
        created_by = str(normalized_metadata.get("created_by") or "workflow_engine").strip() or "workflow_engine"

        with transaction.atomic():
            existing = BatchOperation.objects.select_for_update().filter(id=execution_id).first()
            if existing is None:
                root = BatchOperation.objects.create(
                    id=execution_id,
                    name=name,
                    description=description,
                    operation_type="execute_workflow",
                    target_entity="Workflow",
                    status=BatchOperation.STATUS_PENDING,
                    payload=normalized_payload,
                    config=execution_config,
                    total_tasks=0,
                    created_by=created_by,
                    metadata=normalized_metadata,
                )
                return root, True

            existing_metadata = existing.metadata if isinstance(existing.metadata, dict) else {}
            existing_created_at = existing_metadata.get("created_at")
            if existing_created_at:
                normalized_metadata["created_at"] = existing_created_at
            merged_metadata = dict(existing_metadata)
            merged_metadata.update(normalized_metadata)

            update_fields: list[str] = []
            if existing.name != name:
                existing.name = name
                update_fields.append("name")
            if existing.description != description:
                existing.description = description
                update_fields.append("description")
            if existing.operation_type != "execute_workflow":
                existing.operation_type = "execute_workflow"
                update_fields.append("operation_type")
            if existing.target_entity != "Workflow":
                existing.target_entity = "Workflow"
                update_fields.append("target_entity")
            if existing.created_by != created_by:
                existing.created_by = created_by
                update_fields.append("created_by")
            if existing.payload != normalized_payload:
                existing.payload = normalized_payload
                update_fields.append("payload")
            if existing.config != execution_config:
                existing.config = execution_config
                update_fields.append("config")
            if existing.metadata != merged_metadata:
                existing.metadata = merged_metadata
                update_fields.append("metadata")
            if update_fields:
                existing.save(update_fields=[*update_fields, "updated_at"])
            return existing, False

    @classmethod
    def _mark_workflow_root_operation_queued(
        cls,
        *,
        execution_id: str,
    ) -> None:
        from ...models import BatchOperation

        with transaction.atomic():
            root = BatchOperation.objects.select_for_update().filter(id=execution_id).first()
            if root is None:
                return
            if root.status != BatchOperation.STATUS_PENDING:
                return
            root.status = BatchOperation.STATUS_QUEUED
            root.save(update_fields=["status", "updated_at"])

    @classmethod
    def sync_workflow_root_operation_status(
        cls,
        *,
        execution_id: str,
        workflow_status: str,
        node_id: Any = None,
        trace_id: Any = None,
        error_message: str = "",
        error_code: str = "",
        error_details: Any = None,
    ) -> bool:
        from ...models import BatchOperation

        normalized_execution_id = str(execution_id or "").strip()
        if not normalized_execution_id:
            return False

        normalized_workflow_status = str(workflow_status or "").strip().lower()
        status_map = {
            "pending": BatchOperation.STATUS_PENDING,
            "running": BatchOperation.STATUS_PROCESSING,
            "completed": BatchOperation.STATUS_COMPLETED,
            "failed": BatchOperation.STATUS_FAILED,
            "cancelled": BatchOperation.STATUS_CANCELLED,
        }
        next_status = status_map.get(normalized_workflow_status)
        if next_status is None:
            return False

        if not cls._workflow_root_operation_exists(execution_id=normalized_execution_id):
            if not cls._reconcile_missing_workflow_root_operation(
                execution_id=normalized_execution_id,
                workflow_status=normalized_workflow_status,
                node_id=node_id,
                trace_id=trace_id,
            ):
                return False

        terminal_statuses = {
            BatchOperation.STATUS_COMPLETED,
            BatchOperation.STATUS_FAILED,
            BatchOperation.STATUS_CANCELLED,
        }

        with transaction.atomic():
            root = BatchOperation.objects.select_for_update().filter(id=normalized_execution_id).first()
            if root is None:
                return False

            if root.status in terminal_statuses and root.status != next_status:
                logger.info(
                    "Skipping workflow root status regression",
                    extra={
                        "execution_id": normalized_execution_id,
                        "current_status": root.status,
                        "requested_status": next_status,
                    },
                )
                return False

            metadata = root.metadata if isinstance(root.metadata, dict) else {}
            merged_metadata = dict(metadata)
            merged_metadata["workflow_execution_id"] = normalized_execution_id
            merged_metadata["root_operation_id"] = normalized_execution_id
            merged_metadata["workflow_status"] = normalized_workflow_status

            normalized_node_id = str(node_id or "").strip()
            if normalized_node_id:
                merged_metadata["node_id"] = normalized_node_id
            normalized_trace_id = str(trace_id or "").strip()
            if normalized_trace_id:
                merged_metadata["trace_id"] = normalized_trace_id

            if next_status == BatchOperation.STATUS_FAILED:
                normalized_error_message = str(error_message or "").strip()
                if normalized_error_message:
                    merged_metadata["error"] = normalized_error_message
                normalized_error_code = str(error_code or "").strip()
                if normalized_error_code:
                    merged_metadata["error_code"] = normalized_error_code
                if error_details is not None:
                    merged_metadata["error_details"] = error_details
            elif next_status == BatchOperation.STATUS_COMPLETED:
                merged_metadata.pop("error", None)
                merged_metadata.pop("error_code", None)
                merged_metadata.pop("error_details", None)

            update_fields: list[str] = []
            if root.status != next_status:
                root.status = next_status
                update_fields.append("status")

            now = timezone.now()
            if next_status in terminal_statuses:
                if root.progress != 100:
                    root.progress = 100
                    update_fields.append("progress")
                if root.completed_at is None:
                    root.completed_at = now
                    update_fields.append("completed_at")
            elif next_status == BatchOperation.STATUS_PROCESSING and root.progress == 100:
                root.progress = 0
                update_fields.append("progress")

            if root.metadata != merged_metadata:
                root.metadata = merged_metadata
                update_fields.append("metadata")

            if not update_fields:
                return False

            root.save(update_fields=[*update_fields, "updated_at"])
            return True

    @classmethod
    def _workflow_root_operation_exists(
        cls,
        *,
        execution_id: str,
    ) -> bool:
        from ...models import BatchOperation

        return BatchOperation.objects.filter(id=execution_id).exists()

    @classmethod
    def _reconcile_missing_workflow_root_operation(
        cls,
        *,
        execution_id: str,
        workflow_status: str,
        node_id: Any = None,
        trace_id: Any = None,
    ) -> bool:
        from apps.templates.workflow.models import WorkflowExecution

        normalized_execution_id = str(execution_id or "").strip()
        if not normalized_execution_id:
            return False

        execution = (
            WorkflowExecution.objects.select_related("workflow_template")
            .filter(id=normalized_execution_id)
            .first()
        )
        if execution is None:
            logger.warning(
                "Workflow reconciliation skipped: execution missing",
                extra={"execution_id": normalized_execution_id},
            )
            return False

        execution_consumer = str(execution.execution_consumer or "").strip() or "workflows"
        lane = "workflows"
        execution_trace_id = str(trace_id or execution.trace_id or "").strip() or None
        execution_node_id = str(node_id or execution.current_node_id or "").strip() or None
        created_by = cls._resolve_workflow_created_by(
            execution_id=normalized_execution_id,
            execution=execution,
        )

        message = cls._build_execution_envelope(
            operation_id=normalized_execution_id,
            operation_type="execute_workflow",
            entity="Workflow",
            target_databases=[],
            payload_data={"execution_id": normalized_execution_id},
            execution_config={
                "batch_size": 100,
                "timeout_seconds": 300,
                "retry_count": 1,
                "priority": "normal",
                "idempotency_key": normalized_execution_id,
            },
            metadata={
                "created_by": created_by,
                "template_id": str(execution.workflow_template_id) if execution.workflow_template_id else None,
                "tags": ["workflow", "reconciled_projection"],
                "workflow_execution_id": normalized_execution_id,
                "node_id": execution_node_id,
                "root_operation_id": normalized_execution_id,
                "execution_consumer": execution_consumer,
                "lane": lane,
                "trace_id": execution_trace_id,
            },
        )

        _, created = cls._upsert_workflow_root_operation(
            execution_id=normalized_execution_id,
            message_payload=message,
        )

        try:
            redis_client.add_timeline_event(
                normalized_execution_id,
                event="projection.repaired",
                service="orchestrator",
                metadata={
                    "workflow_execution_id": normalized_execution_id,
                    "root_operation_id": normalized_execution_id,
                    "execution_consumer": execution_consumer,
                    "lane": lane,
                    "workflow_status": str(workflow_status or "").strip().lower(),
                    "repair_reason": "missing_root_projection",
                    "projection_created": created,
                },
                trace_id=execution_trace_id,
                workflow_execution_id=normalized_execution_id,
                node_id=execution_node_id,
            )
        except Exception:
            pass

        logger.warning(
            "Workflow root projection reconciled",
            extra={
                "execution_id": normalized_execution_id,
                "workflow_status": str(workflow_status or "").strip().lower(),
                "projection_created": created,
            },
        )
        return True

    @classmethod
    def _enqueue_workflow_outbox_intent(
        cls,
        *,
        operation_id: str,
        message_payload: dict[str, Any],
        stream_name: str,
    ):
        from ...models import WorkflowEnqueueOutbox

        normalized_stream_name = str(stream_name or "").strip()
        if not normalized_stream_name:
            raise ValueError("stream_name must be non-empty")

        normalized_payload = message_payload if isinstance(message_payload, dict) else {}

        with transaction.atomic():
            existing = WorkflowEnqueueOutbox.objects.select_for_update().filter(operation_id=operation_id).first()
            if existing is not None:
                return existing, False

            try:
                entry = WorkflowEnqueueOutbox.objects.create(
                    operation_id=operation_id,
                    stream_name=normalized_stream_name,
                    message_payload=normalized_payload,
                    next_retry_at=timezone.now(),
                )
                return entry, True
            except IntegrityError:
                existing = WorkflowEnqueueOutbox.objects.select_for_update().filter(operation_id=operation_id).first()
                if existing is None:
                    raise
                return existing, False

    @classmethod
    def _publish_workflow_queued_event_from_message(
        cls,
        *,
        execution_id: str,
        message_payload: dict[str, Any],
    ) -> None:
        payload = message_payload if isinstance(message_payload, dict) else {}
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        execution_consumer = str(metadata.get("execution_consumer") or "").strip() or "workflows"
        lane = str(metadata.get("lane") or "").strip() or execution_consumer

        event_kwargs: dict[str, Any] = {
            "operation_id": execution_id,
            "state": "QUEUED",
            "microservice": "orchestrator",
            "queue": cls.QUEUE_KEY,
            "workflow_execution_id": execution_id,
            "node_id": metadata.get("node_id"),
            "trace_id": metadata.get("trace_id"),
            "execution_consumer": execution_consumer,
            "lane": lane,
        }
        for field_name in ("priority", "role", "server_affinity", "deadline_at"):
            value = metadata.get(field_name)
            if value:
                event_kwargs[field_name] = value

        event_publisher.publish(**event_kwargs)

    @classmethod
    def _record_sync_workflow_enqueue_backlog_metrics(
        cls,
        *,
        now: datetime | None = None,
    ) -> None:
        from ...models import WorkflowEnqueueOutbox

        snapshot_now = now or timezone.now()
        grouped_rows: dict[tuple[str, str, str, str], dict[str, float]] = {}

        try:
            pending_rows = WorkflowEnqueueOutbox.objects.filter(
                status=WorkflowEnqueueOutbox.STATUS_PENDING
            ).values("message_payload", "next_retry_at", "dispatch_attempts")

            for row in pending_rows:
                payload = row.get("message_payload")
                if not isinstance(payload, dict):
                    continue
                metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
                priority = str(metadata.get("priority") or "").strip().lower() or "unknown"
                role = str(metadata.get("role") or "").strip().lower() or "unknown"
                server_affinity = str(metadata.get("server_affinity") or "").strip().lower() or "shared"

                # Track only scheduling-aware backlog rows relevant to sync workload.
                if role == "unknown" and priority == "unknown" and server_affinity == "shared":
                    continue

                dispatch_attempts = int(row.get("dispatch_attempts") or 0)
                backlog_status = "retrying" if dispatch_attempts > 0 else "queued"
                key = (backlog_status, priority, role, server_affinity)
                aggregate = grouped_rows.setdefault(
                    key,
                    {
                        "backlog_total": 0.0,
                        "lag_seconds": 0.0,
                    },
                )
                aggregate["backlog_total"] += 1.0

                next_retry_at = row.get("next_retry_at")
                if next_retry_at is not None:
                    lag_seconds = max((snapshot_now - next_retry_at).total_seconds(), 0.0)
                    aggregate["lag_seconds"] = max(aggregate["lag_seconds"], float(lag_seconds))

            metric_rows = [
                {
                    "status": status,
                    "priority": priority,
                    "role": role,
                    "server_affinity": server_affinity,
                    "backlog_total": values["backlog_total"],
                    "lag_seconds": values["lag_seconds"],
                }
                for (status, priority, role, server_affinity), values in grouped_rows.items()
            ]
            set_pool_master_data_sync_queue_backlog_by_scheduling(rows=metric_rows)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to record sync workflow enqueue backlog metrics: %s", exc)

    @classmethod
    def _dispatch_workflow_outbox_entry(
        cls,
        *,
        outbox_id: int,
    ) -> dict[str, Any]:
        from ...models import WorkflowEnqueueOutbox

        dispatch_now = timezone.now()
        stream_name = ""
        message_payload: dict[str, Any] = {}

        with transaction.atomic():
            outbox = WorkflowEnqueueOutbox.objects.select_for_update().filter(id=outbox_id).first()
            if outbox is None:
                return {
                    "success": False,
                    "stream_message_id": "",
                    "error_code": "OUTBOX_NOT_FOUND",
                    "error_message": "Workflow enqueue outbox entry not found",
                    "dispatched_now": False,
                }
            if outbox.status == WorkflowEnqueueOutbox.STATUS_DISPATCHED:
                return {
                    "success": True,
                    "stream_message_id": outbox.stream_message_id,
                    "error_code": "",
                    "error_message": "",
                    "dispatched_now": False,
                }

            outbox.dispatch_attempts += 1
            outbox.last_attempted_at = dispatch_now
            outbox.save(update_fields=["dispatch_attempts", "last_attempted_at", "updated_at"])

            stream_name = outbox.stream_name
            message_payload = outbox.message_payload if isinstance(outbox.message_payload, dict) else {}

        try:
            stream_message_id = str(
                redis_client.enqueue_operation_stream(message_payload, stream_name=stream_name) or ""
            )
        except Exception as exc:
            error_code = classify_enqueue_error_code(exc)
            error_message = str(exc or "").strip()[:4000]
            with transaction.atomic():
                outbox = WorkflowEnqueueOutbox.objects.select_for_update().filter(id=outbox_id).first()
                if outbox is not None and outbox.status != WorkflowEnqueueOutbox.STATUS_DISPATCHED:
                    backoff_seconds = min(120, 5 * (2 ** max(0, int(outbox.dispatch_attempts) - 1)))
                    outbox.last_error_code = str(error_code or "")[:64]
                    outbox.last_error = error_message
                    outbox.next_retry_at = dispatch_now + timedelta(seconds=backoff_seconds)
                    outbox.save(
                        update_fields=[
                            "last_error_code",
                            "last_error",
                            "next_retry_at",
                            "updated_at",
                        ]
                    )
            return {
                "success": False,
                "stream_message_id": "",
                "error_code": error_code,
                "error_message": error_message or "Failed to dispatch workflow enqueue outbox",
                "dispatched_now": False,
            }

        with transaction.atomic():
            outbox = WorkflowEnqueueOutbox.objects.select_for_update().filter(id=outbox_id).first()
            if outbox is None:
                return {
                    "success": True,
                    "stream_message_id": stream_message_id,
                    "error_code": "",
                    "error_message": "",
                    "dispatched_now": True,
                }
            if outbox.status == WorkflowEnqueueOutbox.STATUS_DISPATCHED:
                return {
                    "success": True,
                    "stream_message_id": outbox.stream_message_id,
                    "error_code": "",
                    "error_message": "",
                    "dispatched_now": False,
                }

            outbox.status = WorkflowEnqueueOutbox.STATUS_DISPATCHED
            outbox.dispatched_at = dispatch_now
            outbox.stream_message_id = stream_message_id[:64]
            outbox.last_error_code = ""
            outbox.last_error = ""
            outbox.next_retry_at = dispatch_now
            outbox.save(
                update_fields=[
                    "status",
                    "dispatched_at",
                    "stream_message_id",
                    "last_error_code",
                    "last_error",
                    "next_retry_at",
                    "updated_at",
                ]
            )
            return {
                "success": True,
                "stream_message_id": outbox.stream_message_id,
                "error_code": "",
                "error_message": "",
                "dispatched_now": True,
            }

    @classmethod
    def dispatch_pending_workflow_enqueue_outbox(
        cls,
        *,
        batch_size: int = 100,
        now: datetime | None = None,
    ) -> dict[str, int]:
        from ...models import WorkflowEnqueueOutbox

        dispatch_now = now or timezone.now()
        normalized_batch_size = max(1, int(batch_size))

        with transaction.atomic():
            claimed_rows = list(
                WorkflowEnqueueOutbox.objects.select_for_update(skip_locked=True)
                .filter(
                    status=WorkflowEnqueueOutbox.STATUS_PENDING,
                    next_retry_at__lte=dispatch_now,
                )
                .order_by("next_retry_at", "id")
                .values("id", "operation_id", "message_payload")[:normalized_batch_size]
            )

        dispatched = 0
        failed = 0
        for row in claimed_rows:
            outbox_id = int(row["id"])
            execution_id = str(row["operation_id"] or "").strip()
            message_payload = row["message_payload"] if isinstance(row["message_payload"], dict) else {}

            dispatch = cls._dispatch_workflow_outbox_entry(outbox_id=outbox_id)
            if not dispatch["success"]:
                failed += 1
                continue

            dispatched += 1
            if execution_id:
                cls._mark_workflow_root_operation_queued(execution_id=execution_id)
                if dispatch.get("dispatched_now"):
                    cls._publish_workflow_queued_event_from_message(
                        execution_id=execution_id,
                        message_payload=message_payload,
                    )

        cls._record_sync_workflow_enqueue_backlog_metrics(now=dispatch_now)

        return {
            "claimed": len(claimed_rows),
            "dispatched": dispatched,
            "failed": failed,
        }

    @classmethod
    def enqueue_extension_install(
        cls,
        database_ids: list[str],
        extension_config: dict,
        created_by: str = "system",
    ) -> EnqueueResult:
        """Deprecated: extension installation via install_extension is removed."""
        logger.warning(
            "install_extension is deprecated; use designer_cli workflow instead",
            extra={"created_by": created_by, "database_count": len(database_ids)},
        )
        return EnqueueResult(
            success=False,
            operation_id="",
            status="error",
            error="install_extension is deprecated; use designer_cli workflow",
            error_code="NOT_SUPPORTED",
        )

    @classmethod
    def enqueue_workflow_execution(
        cls,
        execution_id: str,
        workflow_config: Optional[dict] = None,
    ) -> EnqueueResult:
        """
        Enqueue workflow execution operation.

        Args:
            execution_id: WorkflowExecution ID
            workflow_config: Optional workflow configuration override

        Returns:
            EnqueueResult with execution_id
        """
        data = dict(workflow_config or {})
        data["execution_id"] = execution_id
        scheduling_contract, validation_error = cls._validate_workflow_scheduling_contract(
            execution_id=execution_id,
            workflow_config=data,
        )
        if validation_error is not None:
            logger.warning(
                "Workflow enqueue rejected by scheduling contract validation",
                extra={
                    "execution_id": execution_id,
                    "error_code": validation_error.error_code,
                    "execution_consumer": str(data.get("execution_consumer") or ""),
                },
            )
            return validation_error
        if scheduling_contract:
            data.update(scheduling_contract)

        idempotency_key = str(data.get("idempotency_key") or execution_id).strip() or execution_id
        execution_consumer = str(data.get("execution_consumer") or "").strip() or "workflows"
        enqueue_priority = scheduling_contract.get("priority") or str(data.get("priority") or "normal")
        created_by = cls._resolve_workflow_created_by(
            execution_id=execution_id,
            workflow_config=data,
        )
        message_metadata = {
            "created_by": created_by,
            "template_id": None,
            "tags": ["workflow"],
            "workflow_execution_id": execution_id,
            "node_id": data.get("node_id"),
            "root_operation_id": execution_id,
            "execution_consumer": execution_consumer,
            "lane": "workflows",
            "trace_id": data.get("trace_id"),
        }
        if scheduling_contract:
            message_metadata.update(scheduling_contract)

        message = cls._build_execution_envelope(
            operation_id=execution_id,
            operation_type="execute_workflow",
            entity="Workflow",
            target_databases=[],
            payload_data=data,
            execution_config={
                "batch_size": 100,
                "timeout_seconds": 300,  # 5 minutes for workflow
                "retry_count": 1,
                "priority": enqueue_priority,
                "idempotency_key": idempotency_key,
            },
            metadata=message_metadata,
        )

        try:
            with transaction.atomic():
                cls._upsert_workflow_root_operation(
                    execution_id=execution_id,
                    message_payload=message,
                )
                outbox_entry, _created = cls._enqueue_workflow_outbox_intent(
                    operation_id=execution_id,
                    message_payload=message,
                    stream_name=redis_client.STREAM_WORKFLOWS,
                )

            dispatch = cls._dispatch_workflow_outbox_entry(outbox_id=outbox_entry.id)
            if not dispatch["success"]:
                cls._record_sync_workflow_enqueue_backlog_metrics()
                logger.error(
                    "Workflow enqueue outbox dispatch failed",
                    extra={
                        "execution_id": execution_id,
                        "outbox_id": outbox_entry.id,
                        "error_code": dispatch.get("error_code"),
                    },
                )
                return EnqueueResult(
                    success=False,
                    operation_id=execution_id,
                    status="error",
                    error=str(dispatch.get("error_message") or "Failed to dispatch workflow enqueue outbox"),
                    error_code=str(dispatch.get("error_code") or "ENQUEUE_DISPATCH_FAILED"),
                )

            cls._mark_workflow_root_operation_queued(execution_id=execution_id)

            if dispatch["dispatched_now"]:
                cls._publish_workflow_queued_event_from_message(
                    execution_id=execution_id,
                    message_payload=message,
                )
            cls._record_sync_workflow_enqueue_backlog_metrics()

            msg_id = str(dispatch["stream_message_id"] or "")

            logger.info(f"Workflow execution {execution_id} enqueued")

            return EnqueueResult(
                success=True,
                operation_id=execution_id,
                status="queued",
                metadata={
                    "stream_message_id": msg_id,
                    "outbox_id": outbox_entry.id,
                    "root_operation_id": execution_id,
                },
            )

        except Exception as exc:
            cls._record_sync_workflow_enqueue_backlog_metrics()
            logger.error(f"Error enqueueing workflow: {exc}", exc_info=True)
            return EnqueueResult(
                success=False,
                operation_id=execution_id,
                status="error",
                error=str(exc),
                error_code=classify_enqueue_error_code(exc),
            )

    @classmethod
    def enqueue_cluster_sync(
        cls,
        cluster_id: str,
        operation_id: Optional[str] = None,
        created_by: str = "system",
    ) -> EnqueueResult:
        """
        Enqueue cluster synchronization operation.

        Args:
            cluster_id: Cluster UUID to sync
            operation_id: Optional existing operation ID
            created_by: User who initiated the sync

        Returns:
            EnqueueResult with operation_id

        Note:
            Payload includes full cluster data for Go Worker:
            - ras_server: RAS server address (host:port)
            - ras_cluster_uuid: UUID of cluster in RAS (may be empty)
            - cluster_name: Cluster name
            - cluster_user, cluster_pwd: Credentials (optional)
        """
        from apps.databases.models import Cluster

        op_id = operation_id or str(uuid.uuid4())

        # Get cluster from DB
        try:
            cluster = Cluster.objects.get(id=cluster_id)
        except Cluster.DoesNotExist:
            logger.error(f"Cluster not found: {cluster_id}")
            return EnqueueResult(
                success=False,
                operation_id=op_id,
                status="error",
                error=f"Cluster {cluster_id} not found",
                error_code="NOT_FOUND",
            )

        # Idempotency check - prevent concurrent sync for same cluster
        sync_lock_key = f"sync_cluster:{cluster_id}"
        lock_acquired = redis_client.acquire_lock(task_id=sync_lock_key, ttl_seconds=900)  # 15 minutes

        if not lock_acquired:
            logger.warning(f"Cluster {cluster_id} sync already in progress (duplicate submission)")
            return EnqueueResult(
                success=False,
                operation_id=op_id,
                status="duplicate",
                error=f"Cluster {cluster.name} sync already in progress",
                error_code="DUPLICATE",
            )

        # Build payload with full cluster data for Worker
        ras_server = str(cluster.ras_server or "").strip()
        if getattr(cluster, "ras_host", None):
            ras_host = str(cluster.ras_host or "").strip()
            ras_port = int(cluster.ras_port or 1545) if getattr(cluster, "ras_port", None) else 1545
            if ras_host:
                ras_server = f"{ras_host}:{ras_port}"

        cluster_data = {
            "cluster_id": str(cluster.id),
            "cluster_name": cluster.name,
            "ras_server": ras_server,
            "ras_cluster_uuid": str(cluster.ras_cluster_uuid) if cluster.ras_cluster_uuid else "",
            "cluster_user": cluster.cluster_user or "",
            "cluster_pwd": cluster.cluster_pwd or "",
        }

        message = cls._build_execution_envelope(
            operation_id=op_id,
            operation_type="sync_cluster",
            entity="Cluster",
            target_databases=[],
            payload_data=cluster_data,
            execution_config={
                "batch_size": 50,
                "timeout_seconds": 180,
                "retry_count": 3,
                "priority": "normal",
                "idempotency_key": op_id,
            },
            metadata={
                "created_by": created_by,
                "template_id": None,
                "tags": ["cluster", "sync"],
            },
        )

        try:
            # Acquire enqueue lock (separate key from Worker's task lock)
            # This prevents duplicate enqueue, Worker handles processing idempotency
            redis_client.acquire_enqueue_lock(task_id=op_id, ttl_seconds=3600)  # 1 hour

            msg_id = redis_client.enqueue_operation_stream(message)

            event_publisher.publish(
                operation_id=op_id,
                state="QUEUED",
                microservice="orchestrator",
                queue=cls.QUEUE_KEY,
                cluster_id=cluster_id,
            )

            # Publish flow event for Service Mesh visualization
            flow_publisher.publish_flow(
                operation_id=op_id,
                current_service="orchestrator",
                status="processing",
                message=f"Cluster sync queued: {cluster.name}",
                operation_type="sync_cluster",
                operation_name=f"Sync {cluster.name}",
                path=["frontend", "api-gateway", "orchestrator", "worker"],
                metadata={
                    "cluster_id": cluster_id,
                    "cluster_name": cluster.name,
                    "queue": cls.QUEUE_KEY,
                },
            )

            logger.info(
                f"Cluster sync operation {op_id} enqueued",
                extra={
                    "operation_id": op_id,
                    "cluster_id": cluster_id,
                    "cluster_name": cluster.name,
                    "ras_server": cluster.ras_server,
                },
            )

            return EnqueueResult(
                success=True,
                operation_id=op_id,
                status="queued",
                metadata={
                    "cluster_id": cluster_id,
                    "cluster_name": cluster.name,
                    "stream_message_id": msg_id,
                },
            )

        except Exception as exc:
            logger.error(f"Error enqueueing cluster sync: {exc}", exc_info=True)

            # Best-effort cleanup: allow immediate retry after enqueue failure.
            try:
                redis_client.release_enqueue_lock(task_id=op_id)
            except Exception:
                pass
            try:
                redis_client.release_lock(task_id=sync_lock_key)
            except Exception:
                pass

            return EnqueueResult(
                success=False,
                operation_id=op_id,
                status="error",
                error=str(exc),
                error_code=classify_enqueue_error_code(exc),
            )
