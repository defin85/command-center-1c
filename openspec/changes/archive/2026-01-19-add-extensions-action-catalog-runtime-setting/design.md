## Context (Контекст)
Платформа уже умеет:
- Schema-driven driver catalogs (ibcmd/cli) и endpoint выполнения ibcmd: `POST /api/v2/operations/execute-ibcmd-cli/`
- Endpoint выполнения workflow: `POST /api/v2/workflows/execute-workflow/`
- Bulk-семантику для операций (одна batch operation, много per-database tasks)
- Streams для прогресса UI (Operations SSE)

Stage 9 (Extensions) требует UI, который умеет управлять жизненным циклом расширений на 1+ базах, переиспользуя существующие operations/workflows и streaming.

## Goals / Non-Goals (Цели / Не цели)
- Goals (Цели):
  - Не хардкодить привязки команд для управления расширениями во фронтенде.
  - Дать операторам возможность настраивать, какие drivers/commands/workflows реализуют каждое действие над расширениями.
  - Поддержать как single-database, так и bulk execution.
  - Оставить безопасность на уровне существующих RBAC + фильтрации driver catalog + dangerous-confirm gates.
  - Хранить snapshot расширений в Postgres для быстрых чтений UI.
- Non-Goals (Не цели):
  - Перестраивать систему driver catalog или редактор схем команд.
  - Вводить новый execution engine (Go Worker остаётся единственным engine).
  - Делать action catalog security boundary (эндпоинты выполнения всё равно применяют RBAC).

## Decisions (Решения)
- Хранить маппинги действий в БД как RuntimeSetting:
  - Key: `ui.action_catalog`
  - Value: JSON "action catalog" (v1) с секцией `extensions`.
- Экспортировать "effective" action catalog для текущего пользователя:
  - Новый API endpoint (path TBD): `GET /api/v2/ui/action-catalog/`
  - Фильтрация действий по:
    - Ссылкам на driver catalog entries (существует, не disabled, видимо пользователю)
    - Ссылкам на workflows (существует, active, valid, executable пользователем)
    - Environment / role constraints (переиспользуем правила фильтрации driver catalog)
- Поддерживаемые executors в каталоге:
  - `ibcmd_cli` -> `POST /api/v2/operations/execute-ibcmd-cli/`
  - `designer_cli` -> `POST /api/v2/operations/execute/` (`operation_type=designer_cli`)
  - `workflow` -> `POST /api/v2/workflows/execute-workflow/`
- Deactivation и deletion — разные действия (никогда не объединяем).
- Bulk-семантика:
  - `ibcmd_cli`: передаём `database_ids` (per_database), чтобы создать N tasks.
  - `workflow`: передаём `target_database_ids` (или эквивалент) внутри `input_context`.

## Action Catalog Schema (v1) (Схема)
Хранится в RuntimeSetting `ui.action_catalog`.

High-level structure (структура верхнего уровня):
```json
{
  "catalog_version": 1,
  "extensions": {
    "actions": [
      {
        "id": "extensions.list",
        "label": "Список расширений",
        "contexts": ["database_card", "bulk_page"],
        "executor": {
          "kind": "ibcmd_cli",
          "driver": "ibcmd",
          "command_id": "infobase.extension.list",
          "mode": "guided",
          "fixed": {
            "timeout_seconds": 300,
            "confirm_dangerous": false
          }
        }
      }
    ]
  }
}
```

Executor payload mapping rules (правила маппинга payload):
- `ibcmd_cli` executor:
  - `command_id` маппится на `ExecuteIbcmdCliOperationRequestSerializer.command_id`
  - `mode`, `params`, `additional_args`, `stdin`, `confirm_dangerous`, `timeout_seconds` маппятся 1:1
  - Целевые базы берутся из UI (карточка базы -> 1 id; bulk -> список)
- `workflow` executor:
  - `workflow_id` маппится на `ExecuteWorkflowRequestSerializer.workflow_id`
  - `input_context` собирается из UI и ОБЯЗАН включать target database ids для bulk

Note: каталог хранит UI-метаданные (label, contexts) и execution bindings; схемы параметров команд берём из driver catalogs (`/api/v2/operations/driver-commands/`).

## Validation / Resolution (Валидация / Разрешение)
- Update-time validation (staff-only update flow):
  - Валидируем JSON shape и обязательные поля (`catalog_version`, `actions[*].id`, `executor.kind`, и т.д.)
  - Валидируем ссылки:
    - `ibcmd_cli`/`designer_cli`: `command_id` ОБЯЗАН существовать в effective driver catalog
    - `workflow`: `workflow_id` ОБЯЗАН существовать и быть active + valid
- Read-time validation:
  - Если значение в БД некорректно, fail closed (возвращаем пустой `extensions.actions`) и логируем диагностику.
  - Если конкретное action невалидно (unknown command/workflow), исключаем его из effective catalog.

## Snapshot Storage (Postgres) (Хранение snapshot)
Опционально, но поддерживается для ускорения UI:
- Новая модель/таблица (name TBD): per-database "extensions snapshot"
  - `database_id` (FK)
  - `snapshot` (JSON)
  - `updated_at`
  - `source_operation_id` (опционально, для audit)
- Обновляем после успешного выполнения настроенного действия "sync/list extensions".

## Migration Plan (План миграции)
1) Добавить RuntimeSetting definition + default empty action catalog.
2) Добавить API endpoint, который возвращает effective action catalog для текущего пользователя.
3) Добавить UI:
   - Карточка базы: вкладка/панель Extensions (single DB)
   - Bulk page: действия над расширениями для выбранных баз
4) Добавить snapshot persistence + пайплайн обновления.
5) Добавить тесты и документацию.

## Open Questions (Открытые вопросы)
- Endpoint naming: `GET /api/v2/ui/action-catalog/` vs ресурсный endpoint (например, `/api/v2/extensions/action-catalog/`).
- Нужен ли backend endpoint "execute action by id", чтобы ещё сильнее уменьшить coupling фронтенда?
- Key naming: оставить `ui.action_catalog` (multi-domain) vs `ui.extensions.action_catalog` (узко).
- File references для install/update действий: artifacts (`artifact://<storage_key>`) vs uploaded files (резолвить до общего filesystem path).
