## 0. Coordination with sibling changes
- [x] 0.1 Зафиксировать стабильный runtime контракт `distribution_artifact.v1` (версия, обязательные поля coverage/balance/allocations) как upstream input для document-policy и atomic workflow compiler.
- [x] 0.2 Добавить integration checks, подтверждающие, что downstream paths (`document_plan_artifact`, atomic workflow compile) не обходят `distribution_artifact` через raw `run_input`.
- [x] 0.3 Зафиксировать delivery order: сначала full-chain distribution invariants, затем document-policy compile, затем atomic workflow expansion.

## 1. Contract and Domain Baseline
- [x] 1.1 Зафиксировать в спеках canonical full-distribution инварианты для create-run execution path (active DAG coverage + balance preservation).
- [x] 1.2 Зафиксировать, что publication payload для create-run формируется из runtime distribution artifacts, а не из произвольного raw `run_input`.
- [x] 1.3 Зафиксировать machine-readable fail-closed taxonomy для нарушений инвариантов распределения.
- [x] 1.4 Зафиксировать `provenance-only` политику для `run_input.documents_by_database` (принимается для аудита, но не влияет на итоговый publication payload).

## 2. Runtime Algorithm Wiring
- [x] 2.1 Подключить `distribute_top_down` к шагу `pool.distribution_calculation.top_down` с учётом active topology version (`effective_from/effective_to`) и edge constraints (`weight/min/max`).
- [x] 2.2 Подключить bottom-up агрегацию к шагу `pool.distribution_calculation.bottom_up` с расчётом root convergence по active topology.
- [x] 2.3 Сохранять детерминированный distribution artifact в execution context (узлы/рёбра/итоги), пригодный для дальнейшей публикации и отчётности.
- [x] 2.4 Добавить schema validation для обязательных полей `distribution_artifact.v1` перед reconciliation/publication и downstream handoff.

## 3. Reconciliation and Fail-Closed Gate
- [x] 3.1 Перевести reconciliation на проверку канонических distribution artifacts вместо summary-only сверки.
- [x] 3.2 При нарушении full-distribution инвариантов завершать run fail-closed до publication step с machine-readable кодом.
- [x] 3.3 Гарантировать, что publication step не стартует, если distribution/reconciliation не подтвердили полное покрытие и сходимость суммы.

## 4. Publication Payload Source-of-Truth
- [x] 4.1 Собирать base publication input для create-run из distribution artifact (без обхода через raw `run_input`); document-chain детализация для per-document/invoice выполняется downstream change `add-02-pool-document-policy`.
- [x] 4.2 Сохранить совместимость retry failed-subset контракта, но явно зафиксировать связь retry с ранее рассчитанным run distribution state.
- [x] 4.3 Сохранять `run_input.documents_by_database` только как provenance/diagnostics snapshot без влияния на publication payload.

## 5. Validation and Tests
- [x] 5.1 Добавить unit-тесты на top-down full-chain distribution (многоуровневый граф, min/max, rounding remainder, deterministic seed).
- [x] 5.2 Добавить unit/интеграционные тесты на bottom-up convergence (accepted rows -> root total) и fail-closed при balance mismatch.
- [x] 5.3 Добавить API/e2e тесты на блокировку publication при distribution coverage gaps и на корректный machine-readable код ошибки.
- [x] 5.4 Обновить regression tests для create-run/retry, чтобы подтвердить source-of-truth semantics publication payload.

## 6. Quality Gates
- [x] 6.1 Прогнать `openspec validate update-01-pool-run-full-chain-distribution --strict --no-interactive`.
- [x] 6.2 Прогнать целевые backend/worker/frontend тесты, затронутые изменением runtime semantics.
