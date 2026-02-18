# Release Notes — 2026-02-17

## add-poolops-driver-workflow-runtime-fail-closed (3.6)

### Что изменилось
- Добавлен runtime setting `pools.projection.publication_hardening_cutoff_utc`.
- Формат значения: RFC3339 UTC (`YYYY-MM-DDTHH:MM:SSZ` или `+00:00`).
- Для `workflow_core` run-ов с `publication_step_state=null` включена staged-логика:
  - `projection_timestamp < cutoff` → сохраняется legacy terminal projection (`published/partial_success` по `failed_targets`);
  - `projection_timestamp >= cutoff` → применяется hardening (`failed`, если publication completion не подтверждён).

### Canonical projection timestamp
Используется формула:
1. `workflow_execution.started_at`
2. `workflow_execution.created_at` (если поле доступно в модели)
3. `pool_run.created_at`

### Rollback-safe поведение
- Пустой/невалидный cutoff трактуется как “cutoff не задан”, historical fallback остаётся включён.
