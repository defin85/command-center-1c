"""UI table metadata part."""

from __future__ import annotations

TABLE_METADATA_PART = {
    "artifacts": {
        "table_id": "artifacts",
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
                "key": "kind",
                "label": "Kind",
                "group_key": "core",
                "group_label": "Core",
                "sortable": True,
                "data_type": "enum",
                "filter": {
                    "type": "select",
                    "operators": ["eq", "in"],
                    "options": [
                        {"value": "extension", "label": "Расширение конфигурации (.cfe)"},
                        {"value": "config_xml", "label": "Выгрузка конфигурации XML (.xml)"},
                        {"value": "dt_backup", "label": "Выгрузка ИБ (.dt)"},
                        {"value": "epf", "label": "Внешняя обработка (.epf)"},
                        {"value": "erf", "label": "Внешний отчет (.erf)"},
                        {"value": "ibcmd_package", "label": "Пакет IBCMD (.zip)"},
                        {"value": "ras_script", "label": "Скрипт RAS (.txt)"},
                        {"value": "other", "label": "Другое"},
                    ],
                },
                "server_field": "kind",
            },
            {
                "key": "tags",
                "label": "Tags",
                "group_key": "meta",
                "group_label": "Meta",
                "sortable": False,
                "data_type": "text",
                "filter": {"type": "text", "operators": ["contains", "eq"], "placeholder": "Tag"},
                "server_field": "tag",
            },
            {
                "key": "created_at",
                "label": "Created",
                "group_key": "time",
                "group_label": "Time",
                "sortable": True,
                "data_type": "datetime",
                "filter": {"type": "date", "operators": ["eq", "before", "after"], "placeholder": "Created"},
                "server_field": "created_at",
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
