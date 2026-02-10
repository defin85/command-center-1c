## Context
Существующая реализация объединяет в одном домене две конкурирующие execution-модели:
- template-based execution,
- action-catalog-based execution.

Это приводит к расхождению API, UI, RBAC, validation и операционного поведения. Пользовательский фокус смещается: вместо управления templates происходит настройка отдельного action runtime слоя.

## Goals
- Сделать `templates` единственным source of truth атомарных операций.
- Разделить ответственность экранов:
  - Workflow: запуск цепочек атомарных операций.
  - Operations/manual execution: запуск конкретных атомарных операций по target-ам.
- Удалить `action_catalog` как runtime и management контракт полностью.
- Выполнить one-shot cutover без fallback и dual-path.

## Non-Goals
- Этапный rollout с совместимостью старых action-catalog клиентов.
- Сохранение mixed-surface `/templates` UX.
- Временные адаптеры, проксирующие `action_id -> template_id`.

## Decisions
### 1. Canonical Runtime Contract
- Единственный исполняемый объект: `operation_exposure(surface="template")` + связанный `operation_definition`.
- `surface="action_catalog"` удаляется из domain model и API-контрактов.

### 2. Manual Operations Contract (UI)
- В UI фиксируется явный перечень ручных операций домена extensions (например, `extensions.sync`, `extensions.set_flags`).
- Для каждой ручной операции запуск выполняется только через выбранный `template_id` и runtime input.
- Бизнес-семантика ручной операции задаётся контрактом UI + backend validation, а не alias/capability action catalog.

### 3. Plan/Apply Contract for Extensions
- `POST /api/v2/extensions/plan/` принимает template-based payload.
- Для `extensions.set_flags` обязательны `template_id`, `extension_name`, `flags_values`, `apply_mask`.
- Backend fail-closed валидирует:
  - template существует и опубликован,
  - template совместим с выбранной ручной операцией,
  - runtime input корректно маппится в executor params.

### 4. Templates UI
- `/templates` становится templates-only экраном.
- Существующий editor shell сохраняется, но без action-catalog ветки и surface переключателя.
- Настройка параметров/биндингов шаблона делается в том же editor flow.

### 5. Databases/Extensions UI
- `/extensions` и `/databases` больше не читают `ui/action-catalog`.
- Все ручные запуски extensions-операций используют template-based plan/apply pipeline.
- UI тексты и подсказки отражают единственную модель: templates-only.

### 6. Decommission Semantics
- Endpoint `GET /api/v2/ui/action-catalog/` удаляется из поддерживаемого API.
- Запросы с legacy `action_id` не адаптируются и отклоняются fail-closed.
- Контракты и документация обновляются синхронно в одном релизе.

## Trade-offs
- Плюсы:
  - один source of truth,
  - меньше связности между UI и backend,
  - детерминированный runtime path,
  - проще сопровождение и аудит.
- Минусы:
  - явный breaking change для legacy-клиентов,
  - большой единоразовый diff по backend/frontend/tests/docs.

## Risks & Mitigations
- Риск: неверная совместимость template/manual operation.
  - Митигировать fail-closed validation + тестами compatibility matrix.
- Риск: регресс UX в `/databases` и `/extensions` после удаления action controls.
  - Митигировать обновлением экранов в том же change и browser regression тестами.
- Риск: зависшие legacy данные action_catalog в БД.
  - Митигировать миграцией decommission + явной диагностикой/cleanup script.

## Migration Plan (Single Step)
1. Обновить API-контракты и backend валидацию на templates-only execution.
2. Удалить action-catalog endpoint/model usage/runtime helpers.
3. Перевести frontend (`/templates`, `/extensions`, `/databases`) на templates-only path.
4. Выполнить data cleanup migration для legacy action_catalog exposures.
5. Обновить docs/tests и выпустить change как единый cutover.

## Open Questions
- Отсутствуют (scope intentionally fixed: полный cutover без совместимости).
