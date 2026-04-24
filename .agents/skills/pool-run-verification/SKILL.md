---
name: pool-run-verification
description: "Use to verify the full pool run flow on a live contour through report and OData evidence."
---

# Pool Run Verification

## What This Skill Does

Пакует повторяемый workflow проверки `pool run -> publication -> OData document verification` на живом контуре.

## When To Use

Используй, когда пользователь просит:

- "прогони полный круг pool run"
- "проверь, что документ создался"
- "скажи номер и дату документа"
- "проверь публикацию через OData"

## Inputs

- `pool_id`
- `pool_workflow_binding_id`
- `tenant_id`
- `period_start`
- `starting_amount`
- UI и OData credentials или уже выставленные env vars

## Outputs

- `run_id`
- terminal status run/report
- `Ref_Key`, номер и дата документа
- подтверждение OData side effects

## Workflow

1. Прочитай live recipe в `DEBUG.md`.
2. Получи JWT через UI auth endpoint.
3. Создай `safe` pool run.
4. Вызови `confirm-publication` с `Idempotency-Key`.
5. Полли report до terminal state.
6. Проверь документ через OData по `Ref_Key`.
7. Сообщи `run_id`, статус, номер и дату документа.

## Success Criteria

- report дошёл до terminal state
- OData подтвердил наличие документа
- пользователь получил номер и дату документа

## Practical Job

Пример: "Прогони новый `safe` run для top-down pool и скажи номер и дату созданного документа."
