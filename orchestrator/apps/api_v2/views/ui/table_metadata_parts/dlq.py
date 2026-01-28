"""UI table metadata part."""

from __future__ import annotations

TABLE_METADATA_PART = {
    "dlq": {
        "table_id": "dlq",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "failed_at",
                "label": "Failed at",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "datetime",
                "filter": {"type": "date", "operators": ["eq", "before", "after"], "placeholder": "Failed at"},
                "server_field": "failed_at",
            },
            {
                "key": "operation_id",
                "label": "Operation",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Operation ID"},
                "server_field": "operation_id",
            },
            {
                "key": "error_code",
                "label": "Error",
                "group_key": "details",
                "group_label": "Details",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Error code"},
                "server_field": "error_code",
            },
            {
                "key": "error_message",
                "label": "Message",
                "group_key": "details",
                "group_label": "Details",
                "sortable": False,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Error message"},
                "server_field": "error_message",
            },
            {
                "key": "worker_id",
                "label": "Worker",
                "group_key": "details",
                "group_label": "Details",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Worker ID"},
                "server_field": "worker_id",
            },
            {
                "key": "actions",
                "label": "Actions",
                "group_key": "actions",
                "group_label": "Actions",
                "sortable": False,
                "data_type": "action",
            },
        ],
    },
}
