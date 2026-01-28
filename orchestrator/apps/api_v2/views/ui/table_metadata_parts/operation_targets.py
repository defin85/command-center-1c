"""UI table metadata part."""

from __future__ import annotations

TABLE_METADATA_PART = {
    "operation_targets": {
        "table_id": "operation_targets",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "name",
                "label": "Database",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Database"},
                "server_field": "name",
            },
            {
                "key": "cluster",
                "label": "Cluster",
                "group_key": "core",
                "group_label": "Core",
                "sortable": False,
                "data_type": "text",
            },
            {
                "key": "status",
                "label": "Status",
                "group_key": "status",
                "group_label": "Status",
                "sortable": True,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "active", "label": "Active"},
                        {"value": "inactive", "label": "Inactive"},
                        {"value": "maintenance", "label": "Maintenance"},
                        {"value": "error", "label": "Error"},
                    ],
                },
                "server_field": "status",
            },
            {
                "key": "last_check_status",
                "label": "Health",
                "group_key": "status",
                "group_label": "Status",
                "sortable": True,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "ok", "label": "OK"},
                        {"value": "degraded", "label": "Degraded"},
                        {"value": "down", "label": "Down"},
                        {"value": "unknown", "label": "Unknown"},
                    ],
                },
                "server_field": "last_check_status",
            },
        ],
    },
}
