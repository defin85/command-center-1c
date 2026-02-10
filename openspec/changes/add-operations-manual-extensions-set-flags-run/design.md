## Context
Операторы работают в двух режимах:
- основной: массовый rollout через workflow,
- fallback: ручной/точечный прогон при авариях и one-off задачах.

В текущей архитектуре ручной fallback для `extensions.set_flags` уже есть в `/extensions`, но отсутствует в `/operations`, где оператор обычно запускает ad-hoc операции.

## Goals
- Добавить ручной fallback-путь в `/operations` без дублирования backend execution path.
- Сохранить единые гарантии drift check, preview provenance и fail-closed validation.
- Не размывать workflow-first модель для массового управления.

## Non-Goals
- Новый backend pipeline вместо `extensions plan/apply`.
- Превращение `/operations` в основной bulk UI для extensions rollout.

## Decision
1. В `/operations` добавить ручной operation type для `extensions.set_flags`.
2. Запуск строить через существующий `extensions plan/apply`:
   - `POST /api/v2/extensions/plan/`
   - `POST /api/v2/extensions/apply/`
3. Перед apply показывать preview (execution plan + binding provenance).
4. UX явно маркирует ручной путь как fallback.

## Data Flow
1. Оператор выбирает базы (как в обычном wizard).
2. В Configure шаге задаёт:
   - `action_id` (из effective catalog),
   - `extension_name` (selector + manual input fallback),
   - runtime flag values,
   - `apply_mask`.
3. UI вызывает `extensions.plan` и показывает preview.
4. После подтверждения UI вызывает `extensions.apply`.
5. UI переводит в `/operations?operation=<id>`.

## Error Handling
- `CONFIGURATION_ERROR`/`VALIDATION_ERROR`: блокирующая ошибка до enqueue.
- `DRIFT_CONFLICT`: показать diff и предложить re-plan/retry.
- `MISSING_ACTION`/`AMBIGUOUS_ACTION` (если применимо): actionable hint про выбор/настройку action.

## Security/RBAC
- Используются те же backend guards, что и для set_flags:
  - `manage_database` permission,
  - для staff mutating: explicit tenant header.

## Risks
- Риск дублирования UX-логики между `/extensions` и `/operations`.
- Риск, что операторы начнут использовать manual path как массовый вместо workflow.

## Mitigations
- Вынести shared plan/apply UI helper (preview + replan/retry) в общий модуль.
- Явно обозначить manual flow как fallback (лейблы/подсказки/ограничения по объёму).
