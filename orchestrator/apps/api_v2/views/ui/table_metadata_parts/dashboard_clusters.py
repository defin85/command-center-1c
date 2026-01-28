"""UI table metadata part."""

from __future__ import annotations

TABLE_METADATA_PART = {
    "dashboard_clusters": {
        "table_id": "dashboard_clusters",
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
            },
            {
                "key": "databases",
                "label": "Databases",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Databases"},
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
                        {"value": "healthy", "label": "healthy"},
                        {"value": "degraded", "label": "degraded"},
                        {"value": "critical", "label": "critical"},
                    ],
                },
            },
        ],
    },
}
