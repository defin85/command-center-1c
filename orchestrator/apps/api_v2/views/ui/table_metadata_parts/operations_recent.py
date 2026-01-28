"""UI table metadata part."""

from __future__ import annotations

TABLE_METADATA_PART = {
    "operations_recent": {
        "table_id": "operations_recent",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "id",
                "label": "ID",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "ID"},
            },
            {
                "key": "name",
                "label": "Name",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Name"},
            },
            {
                "key": "service",
                "label": "Service",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Service"},
            },
            {
                "key": "status",
                "label": "Status",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": True,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "pending", "label": "pending"},
                        {"value": "queued", "label": "queued"},
                        {"value": "processing", "label": "processing"},
                        {"value": "completed", "label": "completed"},
                        {"value": "failed", "label": "failed"},
                        {"value": "cancelled", "label": "cancelled"},
                    ],
                },
            },
            {
                "key": "progress",
                "label": "Progress",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Progress"},
            },
            {
                "key": "durationSeconds",
                "label": "Duration",
                "group_key": "time",
                "group_label": "Time",
                "sortable": True,
                "data_type": "number",
                "filter": {"type": "number", "operators": ["eq", "gt", "lt"], "placeholder": "Duration (s)"},
            },
            {
                "key": "createdAt",
                "label": "Created",
                "group_key": "time",
                "group_label": "Time",
                "sortable": True,
                "data_type": "datetime",
                "filter": {"type": "date", "operators": ["eq", "before", "after"], "placeholder": "Created at"},
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
