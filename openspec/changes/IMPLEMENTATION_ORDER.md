# Порядок реализации change-ов (pool runtime / document policy / execution unification)

Этот документ фиксирует согласованный порядок внедрения активных change-ов по направлению `pool run`.

## 1. `update-01-pool-run-full-chain-distribution` (upstream)
- Роль: базовый расчетный слой.
- Результат: стабильный `distribution_artifact.v1` + fail-closed инварианты полного распределения.
- Причина первого приоритета: без него downstream слои не имеют канонического источника распределенных сумм.

## 2. `add-02-pool-document-policy` (middle layer)
- Роль: доменная конфигурация документов и compile document chains.
- Результат: стабильный `document_policy.v1` + `document_plan_artifact.v1`.
- Зависимость: использует `distribution_artifact.v1` из шага 1.

## 3. `refactor-03-unify-platform-execution-runtime` (downstream)
- Роль: platform-wide унификация execution-среды и observability (`/operations`).
- Результат: queue-only production path для workflow execution, root projection в `/operations`, atomic pool workflow compiler.
- Зависимость:
  - Track A (runtime/platform) можно выполнять независимо.
  - Track B (pool atomic expansion) стартует после готовности артефактов шагов 1 и 2.

## Краткое правило handoff
- `update-01...` публикует `distribution_artifact.v1`.
- `add-02...` потребляет `distribution_artifact.v1` и публикует `document_plan_artifact.v1`.
- `refactor-03...` потребляет оба артефакта для атомарного workflow graph compile.
