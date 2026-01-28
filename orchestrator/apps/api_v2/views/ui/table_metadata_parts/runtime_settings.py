"""UI table metadata part."""

from __future__ import annotations

TABLE_METADATA_PART = {
    "runtime_settings": {
        "table_id": "runtime_settings",
        "version": "2025-12-30",
        "columns": [
            {
                "key": "key",
                "label": "Key",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Key"},
            },
            {
                "key": "description",
                "label": "Описание",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Описание"},
            },
            {
                "key": "value",
                "label": "Значение",
                "group_key": "value",
                "group_label": "Value",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Значение"},
            },
            {
                "key": "default",
                "label": "Default",
                "group_key": "value",
                "group_label": "Value",
                "sortable": True,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Default"},
            },
            {
                "key": "range",
                "label": "Диапазон",
                "group_key": "value",
                "group_label": "Value",
                "sortable": False,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Диапазон"},
            },
            {
                "key": "actions",
                "label": "Действия",
                "group_key": "actions",
                "group_label": "Actions",
                "sortable": False,
                "data_type": "action",
            },
        ],
    },
}
