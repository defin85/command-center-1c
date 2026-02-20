## 0. Coordination with sibling changes
- [x] 0.1 Зафиксировать вход `distribution_artifact.v1` как обязательный upstream контракт для compile `document_plan_artifact`.
- [x] 0.2 Зафиксировать выход `document_plan_artifact.v1` как downstream контракт для atomic workflow compiler в `refactor-03-unify-platform-execution-runtime`.
- [x] 0.3 Добавить integration checks на недопустимость bypass (`raw run_input`) для document chain compile в create-run path.

## 1. Contract and Policy Model
- [x] 1.1 Описать и зафиксировать versioned contract `document_policy.v1` (структура цепочек, документы, маппинги реквизитов/табличных частей, link rules, invoice_mode).
- [x] 1.2 Зафиксировать machine-readable taxonomy ошибок policy (`*_POLICY_INVALID`, `*_CHAIN_INVALID`, `*_MAPPING_INVALID`, `*_MISSING_REQUIRED_INVOICE`).
- [x] 1.3 Зафиксировать backward-compatible migration path для существующих run-ов без document-policy.

## 2. Topology Storage and Operator Management
- [x] 2.1 Добавить backend валидацию `edge.metadata.document_policy` в topology snapshot upsert.
- [x] 2.2 Добавить read-path возврата metadata (включая `document_policy`) в graph/topology response для операторского редактирования.
- [x] 2.3 Добавить UI-path редактирования document-policy на рёбрах пула (минимальный operator-friendly редактор + client-side preflight).
- [x] 2.4 Обновить OpenAPI/frontend contract для `node.metadata` и `edge.metadata`, чтобы round-trip metadata (включая `document_policy`) был schema-stable.

## 3. Runtime Planning Layer
- [x] 3.1 Реализовать resolver policy c deterministic precedence (edge-level config -> pool defaults, если заданы).
- [x] 3.2 Добавить компиляцию versioned `document_plan_artifact.v1` из `distribution_artifact.v1` + topology + policy до шага publication.
- [x] 3.3 Зафиксировать fail-closed gate: publication не стартует при невалидной policy/цепочке/маппинге.
- [x] 3.4 Зафиксировать и валидировать обязательные поля `document_plan_artifact.v1` (references/chains/documents/idempotency/compile_summary).

## 4. Publication Execution
- [x] 4.1 Расширить publication payload contract до per-document chain (несколько entity в одной target database) с backward compatibility.
- [x] 4.2 Реализовать обязательное создание связанной счёт-фактуры для policy, где `invoice_mode=required`.
- [x] 4.3 Сохранить selective retry semantics: retry работает от persisted `document_plan_artifact` и не дублирует успешные документы.
- [x] 4.4 Зафиксировать, что atomic execution graph строится downstream из `document_plan_artifact` (scope change `refactor-03-unify-platform-execution-runtime`), без дублирования compile логики в этом change.
- [x] 4.5 Запретить обход document-chain compile через raw `run_input` в create-run path при наличии валидного `document_plan_artifact.v1`.

## 5. Tests
- [x] 5.1 Добавить unit-тесты валидации `document_policy.v1` (валидные/невалидные цепочки, required invoice, mapping rules).
- [x] 5.2 Добавить интеграционные тесты runtime compile (`document_plan_artifact`) и fail-closed gate до publication.
- [x] 5.3 Добавить worker tests для multi-document publication chain и retry на уровне цепочки документов.
- [x] 5.4 Добавить API/UI regression tests для topology metadata read/write и operator error handling.

## 6. Validation
- [x] 6.1 Прогнать `openspec validate add-02-pool-document-policy --strict --no-interactive`.
- [x] 6.2 Прогнать целевые тесты backend/worker/frontend, затронутые новым policy-контрактом.

## 7. Post-review follow-up (осталось доделать)
- [x] 7.1 Закрыть UI-риск round-trip metadata: в `PoolCatalogPage` сохранить `node.metadata`/`edge.metadata` без потери пользовательских полей при редактировании `document_policy`.
- [x] 7.2 Добавить frontend regression test на round-trip topology metadata (включая `edge.metadata.document_policy` и произвольные metadata-поля).
- [x] 7.3 Добавить contract parity test для `PoolRunRetryRequest`, чтобы `target_database_ids` проверялся на соответствие runtime serializer и OpenAPI.
- [x] 7.4 Прогнать целевые backend тесты (`pytest`) в окружении orchestrator и зафиксировать результаты в change.
- [x] 7.5 Прогнать UI smoke/e2e сценарий retry для цепочки с `invoice_mode=required` (проверка, что linkage сохраняется и retry не дублирует успешные шаги).

### 7.x Validation evidence (2026-02-20)
- `/home/egor/code/command-center-1c/.venv/bin/pytest orchestrator/apps/api_v2/tests/test_pool_runs_openapi_contract_parity.py -q` → `9 passed`.
- `cd frontend && npm run test:run -- src/pages/Pools/__tests__/PoolCatalogPage.test.tsx -t "document_policy"` → `3 passed`.
- `cd frontend && npm run test:run -- src/pages/Pools/__tests__/PoolCatalogPage.test.tsx -t "preflight validation fails"` → `2 passed`.
- `cd frontend && npm run test:browser:pools-full-flow` → `2 passed`.
