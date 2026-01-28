"""UI table metadata part."""

from __future__ import annotations

TABLE_METADATA_PART = {
    "workflows": {
        "table_id": "workflows",
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
                "key": "workflow_type",
                "label": "Type",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": True,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "sequential", "label": "sequential"},
                        {"value": "parallel", "label": "parallel"},
                        {"value": "conditional", "label": "conditional"},
                        {"value": "complex", "label": "complex"},
                    ],
                },
                "server_field": "workflow_type",
            },
            {
                "key": "is_active",
                "label": "Status",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "boolean",
                "filter": {"type": "boolean", "operators": ["eq"], "placeholder": "Active"},
                "server_field": "is_active",
            },
            {
                "key": "node_count",
                "label": "Nodes",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "number",
            },
            {
                "key": "updated_at",
                "label": "Updated",
                "group_key": "time",
                "group_label": "Time",
                "sortable": True,
                "data_type": "datetime",
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
