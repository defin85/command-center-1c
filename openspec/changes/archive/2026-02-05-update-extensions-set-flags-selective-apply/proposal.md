# Change: Selective apply для extensions.set_flags (UI switches + apply mask)

## Why
Сейчас `/extensions` даёт одну кнопку `Apply flags policy`, которая применяет policy сразу для трёх флагов (`active`, `safe_mode`, `unsafe_action_protection`). Это неудобно, когда нужно:
- применить только часть флагов (например, только `active`, не трогая `safe_mode`);
- быстро задать значения флагов перед apply (в рамках одного действия), без отдельного ручного редактирования policy.

## What Changes
- UI `/extensions` (drawer расширения):
  - в flow `Apply flags policy` добавляется форма из 3 строк:
    - checkbox “Apply this flag”
    - switch со значением для флага
  - пользователь может применить только выбранные флаги (apply mask).
  - при подтверждении apply UI (при необходимости) upsert'ит policy для выбранных флагов и запускает bulk apply.
- API `POST /api/v2/extensions/plan/`:
  - для `capability="extensions.set_flags"` добавляет `apply_mask` (какие флаги применять).
- Backend execution semantics:
  - при plan/apply для `extensions.set_flags` backend исключает невыбранные флаги из executor параметров (чтобы команда реально не модифицировала их).
  - selective apply доступен только при корректной конфигурации executor (см. design).

## Impact
- Affected specs:
  - `extensions-overview` (UI: apply form + selective apply semantics)
  - `extensions-plan-apply` (API: apply_mask + semantics)
  - `extensions-action-catalog` (constraints for reserved capability executor shape)
- Affected code (ожидаемо):
  - Orchestrator: `apps/api_v2/views/extensions_plan_apply.py`, `apps/runtime_settings/action_catalog.py` (валидация reserved capability)
  - Frontend: `frontend/src/pages/Extensions/Extensions.tsx`
  - Contracts/OpenAPI: `contracts/orchestrator/openapi.yaml` + регенерация клиентов/типов

## Non-Goals
- Добавление отдельных кнопок apply по каждому флагу (остаётся одна кнопка Apply).
- Переписывание/унификация driver catalog для конкретных версий `ibcmd` (используем текущий механизм effective driver catalog).

