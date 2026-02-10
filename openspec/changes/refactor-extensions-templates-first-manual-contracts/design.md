## Context
В текущей реализации у домена extensions есть архитектурное расслоение:
- `templates` используются для workflow/части execution-контуров,
- `action_catalog` используется как runtime-контур ручных запусков в отдельных UI.

Это создаёт неоднозначность "главной точки управления" и конфликт ролей:
- `Workflow` по смыслу должен запускать цепочки атомарных операций,
- `Operations` должен запускать конкретные атомарные операции на выбранных таргетах.

## Goals
- Сделать `templates` единым runtime source of truth атомарных операций в домене extensions.
- В `/operations` ввести явный contract-driven manual flow (hardcoded contracts + user-defined binding).
- Развести UX-роли экранов:
  - `/extensions` — workflow-first bulk rollout,
  - `/operations` — ручной atomic launch.
- Сохранить fail-closed validation и прозрачный preview/provenance.

## Non-Goals
- Удалять action catalog для всех доменов в рамках этого change.
- Переписывать workflow engine.
- Полностью переносить весь extensions UX из `/extensions` в `/operations`.

## Decision
### 1. Source of Truth Matrix
- Атомарные операции extensions ДОЛЖНЫ резолвиться из `operation_exposure(surface=template)`.
- Workflow nodes используют `template_id`.
- Manual operations используют `template_id` + manual contract + runtime bindings.
- `action_catalog` НЕ используется как runtime source для `extensions.*` в `/extensions` и `/databases`.

### 2. Manual Contracts Model (UI-hardcoded)
В frontend вводится hardcoded registry manual contracts для `/operations`.

Минимальная структура контракта:
- `id` (пример: `extensions.set_flags.v1`),
- `target_mode` (single/multi),
- `template_filters` (какой template совместим по executor kind/capability),
- `runtime_input_schema`,
- `binding_slots_schema`,
- `preview_adapter`.

Контракт задаёт "что оператор должен заполнить" и "как это маппится на вызов".

### 3. Template-Based Plan/Apply Contract
Для `extensions.set_flags` manual запуска `POST /api/v2/extensions/plan/` принимает:
- `capability=extensions.set_flags`,
- `template_id`,
- `manual_contract_id`,
- `bindings` (map slot -> template param),
- `flags_values`,
- `apply_mask`,
- `extension_name` (если предусмотрен contract schema).

Backend:
- валидирует published template,
- валидирует binding slots,
- fail-closed при несовместимости template и contract,
- строит effective params только из runtime input + bindings.

### 4. UX Separation
- `/extensions`:
  - основной bulk путь через workflow launch,
  - отслеживание прогресса через `/operations`,
  - без ручного targeted atomic apply в том же drawer.
- `/operations`:
  - ручной запуск атомарной операции по contract-driven flow.

### 5. Migration Strategy
1. Диагностика существующих `action_catalog` exposure для `extensions.*`.
2. Soft stage: предупреждение в UI и логах, но старый путь ещё доступен по флагу.
3. Hard stage: runtime path для `extensions.*` через templates-only; старый path выключен.
4. Cleanup action exposures `extensions.*` и документации по старому flow.

## Risks / Trade-offs
- Риск роста сложности в `/operations` wizard из-за contract/binding UX.
- Риск несовместимых существующих template payload shape.
- Риск регрессии для операторов, привыкших к запуску из `/extensions`.

## Mitigations
- Небольшой стартовый набор manual contracts (только критичные extensions сценарии).
- Жёсткая backend-валидация contract/template compatibility + понятные ошибки.
- Переиспользование общего preview/provenance компонента и e2e regression тестов.
- Пошаговый rollout с feature flag.

## Open Questions
- Нужен ли временный compatibility adapter для `action_id -> template_id` на период миграции?
- Оставляем ли возможность создавать `extensions.*` action exposure в editor только в draft для переходного периода, или блокируем сразу?
