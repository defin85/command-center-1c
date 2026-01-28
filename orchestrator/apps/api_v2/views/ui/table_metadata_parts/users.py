"""UI table metadata part."""

from __future__ import annotations

TABLE_METADATA_PART = {
    "users": {
        "table_id": "users",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "username",
                "label": "Username",
                "group_key": "core",
                "group_label": "Core",
                "sortable": False,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Username"},
                "server_field": "username",
            },
            {
                "key": "email",
                "label": "Email",
                "group_key": "core",
                "group_label": "Core",
                "sortable": False,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Email"},
                "server_field": "email",
            },
            {
                "key": "is_staff",
                "label": "Staff",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "boolean",
                "filter": {"type": "boolean", "operators": ["eq"], "placeholder": "Staff"},
                "server_field": "is_staff",
            },
            {
                "key": "is_active",
                "label": "Active",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "boolean",
                "filter": {"type": "boolean", "operators": ["eq"], "placeholder": "Active"},
                "server_field": "is_active",
            },
            {
                "key": "last_login",
                "label": "Last Login",
                "group_key": "time",
                "group_label": "Time",
                "sortable": False,
                "data_type": "datetime",
            },
            {
                "key": "date_joined",
                "label": "Created",
                "group_key": "time",
                "group_label": "Time",
                "sortable": False,
                "data_type": "datetime",
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
