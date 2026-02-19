## 1. Contract and Domain Baseline
- [ ] 1.1 Зафиксировать в спеках canonical full-distribution инварианты для create-run execution path (active DAG coverage + balance preservation).
- [ ] 1.2 Зафиксировать, что publication payload для create-run формируется из runtime distribution artifacts, а не из произвольного raw `run_input`.
- [ ] 1.3 Зафиксировать machine-readable fail-closed taxonomy для нарушений инвариантов распределения.

## 2. Runtime Algorithm Wiring
- [ ] 2.1 Подключить `distribute_top_down` к шагу `pool.distribution_calculation.top_down` с учётом active topology version (`effective_from/effective_to`) и edge constraints (`weight/min/max`).
- [ ] 2.2 Подключить bottom-up агрегацию к шагу `pool.distribution_calculation.bottom_up` с расчётом root convergence по active topology.
- [ ] 2.3 Сохранять детерминированный distribution artifact в execution context (узлы/рёбра/итоги), пригодный для дальнейшей публикации и отчётности.

## 3. Reconciliation and Fail-Closed Gate
- [ ] 3.1 Перевести reconciliation на проверку канонических distribution artifacts вместо summary-only сверки.
- [ ] 3.2 При нарушении full-distribution инвариантов завершать run fail-closed до publication step с machine-readable кодом.
- [ ] 3.3 Гарантировать, что publication step не стартует, если distribution/reconciliation не подтвердили полное покрытие и сходимость суммы.

## 4. Publication Payload Source-of-Truth
- [ ] 4.1 Собирать `pool_runtime_publication_payload.documents_by_database` из distribution artifact (create-run), а не из raw `run_input`.
- [ ] 4.2 Сохранить совместимость retry failed-subset контракта, но явно зафиксировать связь retry с ранее рассчитанным run distribution state.

## 5. Validation and Tests
- [ ] 5.1 Добавить unit-тесты на top-down full-chain distribution (многоуровневый граф, min/max, rounding remainder, deterministic seed).
- [ ] 5.2 Добавить unit/интеграционные тесты на bottom-up convergence (accepted rows -> root total) и fail-closed при balance mismatch.
- [ ] 5.3 Добавить API/e2e тесты на блокировку publication при distribution coverage gaps и на корректный machine-readable код ошибки.
- [ ] 5.4 Обновить regression tests для create-run/retry, чтобы подтвердить source-of-truth semantics publication payload.

## 6. Quality Gates
- [ ] 6.1 Прогнать `openspec validate update-pool-run-full-chain-distribution --strict --no-interactive`.
- [ ] 6.2 Прогнать целевые backend/worker/frontend тесты, затронутые изменением runtime semantics.
