## 1. Domain Contracts
- [ ] 1.1 Спроектировать canonical `PoolBatch` contract для `receipt` и `sale` intake, включая provenance, batch kind, source metadata, schema/integration references и правило `one batch = one pool_run`.
- [ ] 1.2 Спроектировать отдельный batch settlement lifecycle/read-model, не меняя существующий `PoolRun.status`.
- [ ] 1.3 Зафиксировать traceability contract для документов Command Center через `pool_run_id` и/или регистр расширения, а также отдельный contract для `unattributed` документов.

## 2. Batch Intake
- [ ] 2.1 Описать API/UI контракт intake для batch-backed top-down запуска с явным выбором `pool` и `start_organization`.
- [ ] 2.2 Описать schema-driven нормализацию внешних реестров через `Pool Schema Templates` и подготовить расширение под future integration adapters.
- [ ] 2.3 Описать contract для sale batch intake на leaf-узлах без line-level pairing с исходными receipt rows.

## 3. Factual Balance Projection
- [ ] 3.1 Спроектировать materialized read model по измерениям `pool / organization / edge / quarter / batch`.
- [ ] 3.2 Зафиксировать денежные меры `amount_with_vat`, `amount_without_vat`, `vat_amount`, а также derived counters `incoming`, `outgoing`, `open_balance`.
- [ ] 3.3 Спроектировать minute-scale worker sync path из документов и регистров ИБ с watermark-based polling, freshness metadata и обработкой maintenance / blocked external sessions.
- [ ] 3.4 Спроектировать carry-forward contract для незакрытого остатка на том же узле в следующий квартал.

## 4. Operator Surfaces
- [ ] 4.1 Спроектировать summary/drill-down UI для factual balance без перегруженного diagnostic шума.
- [ ] 4.2 Добавить явную связь `run report -> batch settlement -> factual balance dashboard`.
- [ ] 4.3 Спроектировать операторскую очередь review для `unattributed` документов, требующих разметки.

## 5. Verification
- [ ] 5.1 Добавить backend tests на batch intake, batch/run provenance, projection aggregation, carry-forward и unattributed review queue.
- [ ] 5.2 Добавить frontend tests на batch-backed create-run UX, factual summary/drill-down и batch settlement statuses.
- [ ] 5.3 Подготовить live/dev verification сценарий `receipt batch -> distribution -> factual projection -> sale batch/manual sale capture -> refreshed summary`.

## 6. Research / Rollout
- [ ] 6.1 Исследовать и зафиксировать список бухгалтерских отчётов БП и регистров, с которыми будет сверяться projection.
- [ ] 6.2 Принять policy для случаев, когда одна организация участвует в нескольких пулах одного квартала.
- [ ] 6.3 Подготовить rollout envelope для 700 ИБ: размер worker pool, лимиты polling, lag/freshness SLO и деградация на maintenance окнах.
