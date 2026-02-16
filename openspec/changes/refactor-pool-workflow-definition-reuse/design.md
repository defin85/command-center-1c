## Context
Текущая реализация pool runtime компилирует `plan_key` с включением run-specific данных (`period_start`, `period_end`, `run_input`). В результате один и тот же процесс materialize-ится как новые workflow templates для каждого запуска.

Это противоречит целевой модели workflow runtime:
- definition должен быть переиспользуемым blueprint;
- execution должен быть instance с конкретным входным контекстом.

## Goals
- Разделить стабильный `workflow definition` и per-run `execution snapshot`.
- Уменьшить кардинальность system workflow templates без потери трассируемости.
- Сохранить fail-closed и deterministic свойства pool runtime.
- Сохранить текущий queueing/worker split контракт.

## Non-Goals
- Редизайн safe-flow approval gate.
- Изменение stream topology (`commands:worker:operations`/`commands:worker:workflows`).
- Перевод pool runtime на другой execution backend.

## Decisions
### Decision 1: Двухслойная идентичность (definition vs execution)
- `PoolWorkflowDefinition` описывает структуру процесса.
- `PoolExecutionPlanSnapshot` фиксирует run-specific данные и lineage.
- Один definition может иметь много execution instances.

### Decision 2: Состав `definition_key`
`definition_key` включает только структурные признаки:
- `pool_id` (ограничиваем reuse границей доменного пула для минимального риска);
- `direction`, `mode`;
- версию/содержимое schema template;
- compiled DAG structure;
- workflow binding hint (если задан).

`definition_key` не включает:
- `period_start`, `period_end`;
- `run_input`;
- idempotency key и прочие request-specific поля.

### Decision 3: Immutable execution snapshot
На каждый execution сохраняется snapshot, содержащий:
- run-specific вход (`period_*`, `run_input`, `seed`);
- lineage (`root_workflow_run_id`, `parent_workflow_run_id`, `attempt_number`, `attempt_kind`);
- ссылку на resolved definition (`workflow_template_id`, `workflow_template_version`, `definition_key`).

После создания execution snapshot не мутируется, кроме добавления terminal runtime metadata (status/result/diagnostics), совместимого с текущим контрактом.

### Decision 4: Retry reuse
Retry для run переиспользует тот же definition, если структурные признаки не изменились, и создаёт новый execution с новым snapshot lineage.

### Decision 5: UI политика для system-managed pool templates
`pool.*` runtime templates остаются system-managed и readonly:
- видимы в `/templates` (для пользователей с view правами);
- недоступны для edit/delete в UI и публичном write API.

## Risks / Trade-offs
- Если часть `run_input` фактически меняет DAG shape, исключение `run_input` из `definition_key` может скрыть структурные различия.
  - Mitigation: компилятор обязан строить DAG только из структурных источников; при выявлении run-input-dependent shape — вынести это в явное структурное поле/версию.
- Миграция legacy per-run templates потребует аккуратной совместимости historical provenance.
  - Mitigation: новые execution используют новую схему, старые остаются читаемыми без переписывания истории.
- Рост требований к точности snapshot redaction.
  - Mitigation: использовать уже существующий masked execution plan contract.

## Migration Plan
1. Ввести/задокументировать `definition_key` и split definition/execution semantics.
2. Переключить compile/runtime path на definition reuse.
3. Добавить immutable execution snapshot linkage для новых запусков и retry.
4. Сохранить read compatibility historical executions и legacy template references.
5. Обновить `/templates` UI для явного readonly отображения system-managed pool templates.

## Open Questions
- Нужен ли отдельный cleanup job для устаревших per-run workflow templates после стабилизации новой модели, или достаточно оставить их как historical artifacts?
