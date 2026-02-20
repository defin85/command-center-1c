from __future__ import annotations

import hashlib
import json
from typing import Any

from django.utils import timezone

from ...models import BatchOperation


class OperationsServiceMessageMixin:
    @staticmethod
    def _build_target_database_data(db) -> dict[str, str]:
        """
        Build target database data for operation message.

        Args:
            db: Database model instance

        Returns:
            dict with id, name, cluster_id, ras_infobase_id
        """
        return {
            "id": str(db.id),
            "name": db.name,
            "cluster_id": str(db.cluster_id) if db.cluster_id else "",
            "ras_infobase_id": (
                str(db.ras_infobase_id) if hasattr(db, "ras_infobase_id") and db.ras_infobase_id else str(db.id)
            ),
        }

    @staticmethod
    def _normalize_text(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _normalize_created_at(value: Any) -> str:
        if value is None:
            return timezone.now().isoformat()
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
            except Exception:
                pass
        text = str(value).strip()
        return text or timezone.now().isoformat()

    @staticmethod
    def _normalize_tags(value: Any) -> list[str]:
        if isinstance(value, (list, tuple)):
            tags: list[str] = []
            for raw_tag in value:
                tag = str(raw_tag or "").strip()
                if tag:
                    tags.append(tag)
            return tags
        return []

    @classmethod
    def _build_execution_metadata(
        cls,
        *,
        operation_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        raw_metadata = metadata if isinstance(metadata, dict) else {}
        execution_consumer = cls._normalize_text(raw_metadata.get("execution_consumer")) or "operations"
        lane = cls._normalize_text(raw_metadata.get("lane")) or execution_consumer

        root_operation_id = cls._normalize_text(raw_metadata.get("root_operation_id")) or operation_id

        return {
            "created_by": cls._normalize_text(raw_metadata.get("created_by")) or "system",
            "created_at": cls._normalize_created_at(raw_metadata.get("created_at")),
            "template_id": raw_metadata.get("template_id"),
            "template_exposure_id": raw_metadata.get("template_exposure_id"),
            "template_exposure_revision": raw_metadata.get("template_exposure_revision"),
            "tags": cls._normalize_tags(raw_metadata.get("tags")),
            "workflow_execution_id": raw_metadata.get("workflow_execution_id"),
            "node_id": raw_metadata.get("node_id"),
            "root_operation_id": root_operation_id,
            "execution_consumer": execution_consumer,
            "lane": lane,
            "trace_id": raw_metadata.get("trace_id"),
        }

    @classmethod
    def _build_execution_envelope(
        cls,
        *,
        operation_id: str,
        operation_type: str,
        entity: str,
        target_databases: list[dict[str, Any]],
        payload_data: dict[str, Any] | None = None,
        payload_filters: dict[str, Any] | None = None,
        payload_options: dict[str, Any] | None = None,
        execution_config: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        config = {
            "batch_size": 100,
            "timeout_seconds": 30,
            "retry_count": 3,
            "priority": "normal",
        }
        if isinstance(execution_config, dict):
            config.update(execution_config)

        idempotency_key = cls._normalize_text(config.get("idempotency_key")) or operation_id
        config["idempotency_key"] = idempotency_key

        return {
            "version": cls.VERSION,
            "operation_id": operation_id,
            "batch_id": None,
            "operation_type": operation_type,
            "entity": entity,
            "target_databases": target_databases,
            "payload": {
                "data": payload_data if isinstance(payload_data, dict) else {},
                "filters": payload_filters if isinstance(payload_filters, dict) else {},
                "options": payload_options if isinstance(payload_options, dict) else {},
            },
            "execution_config": config,
            "metadata": cls._build_execution_metadata(operation_id=operation_id, metadata=metadata),
        }

    @classmethod
    def _build_message(cls, operation: BatchOperation) -> dict[str, Any]:
        """
        Build Message Protocol v2.0 message from BatchOperation.

        Args:
            operation: BatchOperation model instance

        Returns:
            dict conforming to Message Protocol v2.0
        """
        payload: Any = operation.payload or {}
        payload_data: dict[str, Any] = {}
        payload_filters: dict[str, Any] = {}
        payload_options: dict[str, Any] = {}

        # Support both payload shapes:
        # 1) Protocol-like: {"data": {...}, "filters": {...}, "options": {...}}
        # 2) Legacy: arbitrary dict rendered from template_data (e.g., designer_cli/ibcmd params)
        if isinstance(payload, dict):
            is_protocol_shape = ("data" in payload) or ("filters" in payload) or (set(payload.keys()) <= {"options"})
            if is_protocol_shape:
                raw_data = payload.get("data", {})
                raw_filters = payload.get("filters", {})
                raw_options = payload.get("options", {})
                payload_data = raw_data if isinstance(raw_data, dict) else {}
                payload_filters = raw_filters if isinstance(raw_filters, dict) else {}
                payload_options = raw_options if isinstance(raw_options, dict) else {}
            else:
                payload_data = payload
                raw_options = payload.get("options")
                if isinstance(raw_options, dict):
                    # Preserve legacy payload shape (drivers may rely on payload.data.options),
                    # but expose scope hints in payload.options for protocol-level routing.
                    for key in ("target_scope", "target_ref"):
                        if key in raw_options:
                            payload_options[key] = raw_options.get(key)

        operation_metadata = operation.metadata if isinstance(operation.metadata, dict) else {}
        operation_id = str(operation.id)
        return cls._build_execution_envelope(
            operation_id=operation_id,
            operation_type=operation.operation_type,
            entity=operation.target_entity,
            target_databases=[cls._build_target_database_data(db) for db in operation.target_databases.all()],
            payload_data=payload_data,
            payload_filters=payload_filters,
            payload_options=payload_options,
            execution_config={
                "batch_size": operation.config.get("batch_size", 100),
                "timeout_seconds": operation.config.get("timeout_seconds", 30),
                "retry_count": operation.config.get("retry_count", 3),
                "priority": operation.config.get("priority", "normal"),
                "idempotency_key": operation_id,
            },
            metadata={
                "created_by": operation.created_by or "system",
                "created_at": operation.created_at,
                "template_id": operation.template_id,
                "template_exposure_id": operation.template_exposure_id,
                "template_exposure_revision": operation.template_exposure_revision,
                "tags": operation_metadata.get("tags", []),
                "workflow_execution_id": operation_metadata.get("workflow_execution_id"),
                "node_id": operation_metadata.get("node_id"),
                "root_operation_id": operation_metadata.get("root_operation_id") or operation_id,
                "execution_consumer": operation_metadata.get("execution_consumer") or "operations",
                "lane": operation_metadata.get("lane") or "operations",
                "trace_id": operation_metadata.get("trace_id"),
            },
        )

    @classmethod
    def _extract_target_scope(cls, payload: Any) -> str:
        if not isinstance(payload, dict):
            return ""
        options = payload.get("options")
        if isinstance(options, dict):
            return str(options.get("target_scope") or "").strip().lower()
        return ""

    @classmethod
    def _compute_global_target_ref(cls, payload: Any) -> str:
        if not isinstance(payload, dict):
            return ""

        options = payload.get("options")
        if isinstance(options, dict):
            explicit = options.get("target_ref")
            if isinstance(explicit, str):
                explicit = explicit.strip()
                if explicit:
                    return explicit

        data_section = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        if not isinstance(data_section, dict):
            return ""

        connection = data_section.get("connection")
        if not isinstance(connection, dict):
            connection = {}

        remote = str(connection.get("remote") or data_section.get("remote") or "").strip().lower()
        pid = connection.get("pid")
        if pid is None:
            pid = data_section.get("pid")
        pid_str = str(pid).strip() if pid is not None else ""

        offline = connection.get("offline")
        if not isinstance(offline, dict):
            offline = data_section.get("offline") if isinstance(data_section.get("offline"), dict) else {}

        offline_ref: dict[str, str] = {}
        for key in ("config", "data", "dbms", "db_server", "db_name", "db_user"):
            value = offline.get(key)
            if value is None:
                continue
            offline_ref[key] = str(value).strip()

        if not remote and not pid_str and not offline_ref:
            return ""

        normalized = {
            "remote": remote,
            "pid": pid_str,
            "offline": offline_ref,
        }
        fingerprint = hashlib.sha256(
            json.dumps(normalized, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return fingerprint[:12]
