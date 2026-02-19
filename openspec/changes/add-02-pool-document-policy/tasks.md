## 0. Coordination with sibling changes
- [ ] 0.1 Зафиксировать вход `distribution_artifact.v1` как обязательный upstream контракт для compile `document_plan_artifact`.
- [ ] 0.2 Зафиксировать выход `document_plan_artifact.v1` как downstream контракт для atomic workflow compiler в `refactor-03-unify-platform-execution-runtime`.
- [ ] 0.3 Добавить integration checks на недопустимость bypass (`raw run_input`) для document chain compile в create-run path.

## 1. Contract and Policy Model
- [ ] 1.1 Описать и зафиксировать versioned contract `document_policy.v1` (структура цепочек, документы, маппинги реквизитов/табличных частей, link rules, invoice_mode).
- [ ] 1.2 Зафиксировать machine-readable taxonomy ошибок policy (`*_POLICY_INVALID`, `*_CHAIN_INVALID`, `*_MAPPING_INVALID`, `*_MISSING_REQUIRED_INVOICE`).
- [ ] 1.3 Зафиксировать backward-compatible migration path для существующих run-ов без document-policy.

## 2. Topology Storage and Operator Management
- [ ] 2.1 Добавить backend валидацию `edge.metadata.document_policy` в topology snapshot upsert.
- [ ] 2.2 Добавить read-path возврата metadata (включая `document_policy`) в graph/topology response для операторского редактирования.
- [ ] 2.3 Добавить UI-path редактирования document-policy на рёбрах пула (минимальный operator-friendly редактор + client-side preflight).
- [ ] 2.4 Обновить OpenAPI/frontend contract для `node.metadata` и `edge.metadata`, чтобы round-trip metadata (включая `document_policy`) был schema-stable.

## 3. Runtime Planning Layer
- [ ] 3.1 Реализовать resolver policy c deterministic precedence (edge-level config -> pool defaults, если заданы).
- [ ] 3.2 Добавить компиляцию versioned `document_plan_artifact.v1` из `distribution_artifact.v1` + topology + policy до шага publication.
- [ ] 3.3 Зафиксировать fail-closed gate: publication не стартует при невалидной policy/цепочке/маппинге.
- [ ] 3.4 Зафиксировать и валидировать обязательные поля `document_plan_artifact.v1` (references/chains/documents/idempotency/compile_summary).

## 4. Publication Execution
- [ ] 4.1 Расширить publication payload contract до per-document chain (несколько entity в одной target database) с backward compatibility.
- [ ] 4.2 Реализовать обязательное создание связанной счёт-фактуры для policy, где `invoice_mode=required`.
- [ ] 4.3 Сохранить selective retry semantics: retry работает от persisted `document_plan_artifact` и не дублирует успешные документы.
- [ ] 4.4 Зафиксировать, что atomic execution graph строится downstream из `document_plan_artifact` (scope change `refactor-03-unify-platform-execution-runtime`), без дублирования compile логики в этом change.
- [ ] 4.5 Запретить обход document-chain compile через raw `run_input` в create-run path при наличии валидного `document_plan_artifact.v1`.

## 5. Tests
- [ ] 5.1 Добавить unit-тесты валидации `document_policy.v1` (валидные/невалидные цепочки, required invoice, mapping rules).
- [ ] 5.2 Добавить интеграционные тесты runtime compile (`document_plan_artifact`) и fail-closed gate до publication.
- [ ] 5.3 Добавить worker tests для multi-document publication chain и retry на уровне цепочки документов.
- [ ] 5.4 Добавить API/UI regression tests для topology metadata read/write и operator error handling.

## 6. Validation
- [ ] 6.1 Прогнать `openspec validate add-02-pool-document-policy --strict --no-interactive`.
- [ ] 6.2 Прогнать целевые тесты backend/worker/frontend, затронутые новым policy-контрактом.
