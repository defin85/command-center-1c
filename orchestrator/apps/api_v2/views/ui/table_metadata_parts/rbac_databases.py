"""UI table metadata part."""

from __future__ import annotations

TABLE_METADATA_PART = {
    "rbac_databases": {
        "table_id": "rbac_databases",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "user_id",
                "label": "User",
                "group_key": "core",
                "group_label": "Core",
                "sortable": False,
                "data_type": "number",
                "filter": {"type": "number", "operators": ["eq"], "placeholder": "User ID"},
                "server_field": "user_id",
            },
            {
                "key": "database",
                "label": "Database",
                "group_key": "core",
                "group_label": "Core",
                "sortable": False,
                "data_type": "text",
            },
            {
                "key": "database_id",
                "label": "Database ID",
                "group_key": "core",
                "group_label": "Core",
                "sortable": False,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Database ID"},
                "server_field": "database_id",
            },
            {
                "key": "level",
                "label": "Level",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "VIEW", "label": "VIEW"},
                        {"value": "OPERATE", "label": "OPERATE"},
                        {"value": "MANAGE", "label": "MANAGE"},
                        {"value": "ADMIN", "label": "ADMIN"},
                    ],
                },
                "server_field": "level",
            },
            {
                "key": "granted_at",
                "label": "Granted At",
                "group_key": "time",
                "group_label": "Time",
                "sortable": False,
                "data_type": "datetime",
            },
            {
                "key": "granted_by",
                "label": "Granted By",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "text",
            },
            {
                "key": "notes",
                "label": "Notes",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "text",
            },
            {
                "key": "actions",
                "label": "Action",
                "group_key": "actions",
                "group_label": "Actions",
                "sortable": False,
                "data_type": "action",
            },
        ],
    },
}
