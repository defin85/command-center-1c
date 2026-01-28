"""UI table metadata part."""

from __future__ import annotations

TABLE_METADATA_PART = {
    "clusters": {
        "table_id": "clusters",
        "version": "2025-12-24",
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
                "key": "ras_server",
                "label": "RAS Server",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "RAS Server"},
                "server_field": "ras_server",
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
                "key": "databases_count",
                "label": "Databases",
                "group_key": "status",
                "group_label": "Status",
                "sortable": True,
                "data_type": "number",
                "filter": {"type": "number", "operators": ["eq", "gt", "lt"], "placeholder": "Databases count"},
                "server_field": "databases_count",
            },
            {
                "key": "last_sync",
                "label": "Last Sync",
                "group_key": "status",
                "group_label": "Status",
                "sortable": True,
                "data_type": "datetime",
                "filter": {"type": "date", "operators": ["eq", "before", "after"], "placeholder": "Last sync"},
                "server_field": "last_sync",
            },
            {
                "key": "credentials",
                "label": "Credentials",
                "group_key": "access",
                "group_label": "Access",
                "sortable": False,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq"],
                    "options": [
                        {"value": "configured", "label": "Configured"},
                        {"value": "missing", "label": "Missing"},
                    ],
                },
                "server_field": "credentials",
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
