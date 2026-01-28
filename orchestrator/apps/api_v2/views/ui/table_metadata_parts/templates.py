"""UI table metadata part."""

from __future__ import annotations

TABLE_METADATA_PART = {
    "templates": {
        "table_id": "templates",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "name",
                "label": "Name",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Name"},
                "server_field": "name",
            },
            {
                "key": "operation_type",
                "label": "Operation Type",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": True,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "designer_cli", "label": "designer_cli"},
                        {"value": "lock_scheduled_jobs", "label": "lock_scheduled_jobs"},
                        {"value": "unlock_scheduled_jobs", "label": "unlock_scheduled_jobs"},
                        {"value": "terminate_sessions", "label": "terminate_sessions"},
                        {"value": "block_sessions", "label": "block_sessions"},
                        {"value": "unblock_sessions", "label": "unblock_sessions"},
                        {"value": "query", "label": "query"},
                        {"value": "sync_cluster", "label": "sync_cluster"},
                        {"value": "health_check", "label": "health_check"},
                    ],
                },
                "server_field": "operation_type",
            },
            {
                "key": "target_entity",
                "label": "Target",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": True,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "database", "label": "database"},
                        {"value": "cluster", "label": "cluster"},
                        {"value": "system", "label": "system"},
                        {"value": "extension", "label": "extension"},
                    ],
                },
                "server_field": "target_entity",
            },
            {
                "key": "is_active",
                "label": "Active",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": True,
                "data_type": "boolean",
                "filter": {"type": "boolean", "operators": ["eq"], "placeholder": "Active"},
                "server_field": "is_active",
            },
            {
                "key": "updated_at",
                "label": "Updated",
                "group_key": "time",
                "group_label": "Time",
                "sortable": True,
                "data_type": "datetime",
                "filter": {"type": "date", "operators": ["eq", "before", "after"], "placeholder": "Updated at"},
                "server_field": "updated_at",
            },
        ],
    },
}
