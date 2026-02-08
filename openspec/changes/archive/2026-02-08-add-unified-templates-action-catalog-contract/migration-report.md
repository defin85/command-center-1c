# Migration Report: add-unified-templates-action-catalog-contract

Дата: 2026-02-08

## Контекст

Для проверки миграции unified persistence (`OperationDefinition` + `OperationExposure`) выполнен backfill в транзакции с откатом (dry-run semantics) на локальной БД после применения миграций.

## Команды проверки

```bash
cd orchestrator
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py backfill_operation_catalog --dry-run
```

Дополнительно для получения детального списка проблем без персистентных изменений:

```bash
cd orchestrator
../.venv/bin/python manage.py shell <<'PY'
from django.db import transaction
from apps.templates.operation_catalog_backfill import run_unified_operation_catalog_backfill
from apps.templates.models import OperationMigrationIssue

with transaction.atomic():
    stats = run_unified_operation_catalog_backfill()
    print(stats.to_dict())
    for issue in OperationMigrationIssue.objects.order_by('created_at').values(
        'source_type', 'source_id', 'tenant_id', 'code', 'severity', 'message', 'details'
    ):
        print(issue)
    transaction.set_rollback(True)
PY
```

## Результаты backfill (dry-run)

- templates_processed: 17
- actions_processed: 5
- definitions_created: 21
- definitions_reused: 1
- exposures_created: 22
- exposures_updated: 0
- issues_created: 2

## Объекты, требующие ручной фиксации

Найдены 2 migration issues (оба `extensions.set_flags`, fail-closed):

1. source_type: `runtime_setting_tenant_override`
   source_id: `IBCMD_SetActiveYes`
   tenant_id: `4d29aa0d-3fcc-41b2-878a-28f84f6f75ec`
   code: `INVALID_SET_FLAGS_TARGET_BINDING`
   message: `target_binding is required for extensions.set_flags`
2. source_type: `runtime_setting_tenant_override`
   source_id: `IBCMD_SetActiveNo`
   tenant_id: `4d29aa0d-3fcc-41b2-878a-28f84f6f75ec`
   code: `INVALID_SET_FLAGS_TARGET_BINDING`
   message: `target_binding is required for extensions.set_flags`

## Рекомендованные действия

1. В `/settings/action-catalog` отредактировать оба actions и заполнить `executor.target_binding.extension_name_param`.
2. Опубликовать actions (publish) после сохранения.
3. Повторно выполнить dry-run backfill и убедиться, что `issues_created=0` для этих alias.
