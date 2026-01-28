"""UI table metadata part."""

from __future__ import annotations

TABLE_METADATA_PART = {
    "rbac_dbms_users": {
        "table_id": "rbac_dbms_users",
        "version": "2026-01-27",
        "columns": [
            {
                "key": "db_username",
                "label": "DBMS User",
                "group_key": "core",
                "group_label": "Core",
                "sortable": False,
                "data_type": "text",
            },
            {
                "key": "cc_user",
                "label": "CC User",
                "group_key": "core",
                "group_label": "Core",
                "sortable": False,
                "data_type": "text",
            },
            {
                "key": "auth_type",
                "label": "Auth",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "enum",
            },
            {
                "key": "is_service",
                "label": "Service",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "boolean",
            },
            {
                "key": "password",
                "label": "Password",
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
