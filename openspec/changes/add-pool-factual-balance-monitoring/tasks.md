## 1. Domain Contracts
- [ ] 1.1 Спроектировать canonical `PoolBatch` contract для `receipt` и `sale` intake, включая provenance, batch kind, source metadata, schema/integration references и правило `one batch = one pool_run`.
- [ ] 1.2 Спроектировать отдельный batch settlement lifecycle/read-model, не меняя существующий `PoolRun.status`.
- [ ] 1.3 Зафиксировать batch-backed idempotency contract для `batch_id + start_organization_id + period + binding revision`, не ломая existing manual `top_down` path.
- [ ] 1.4 Зафиксировать traceability contract для документов Command Center через machine-readable комментарий `CCPOOL:v=1;...`, включая policy для multi-pool attribution, stable retry/update semantics и отдельный contract для `unattributed` документов.

## 2. Batch Intake
- [ ] 2.1 Описать API/UI контракт intake для batch-backed top-down запуска с явным выбором `pool`, `batch_id` и `start_organization`, сохранив existing manual `top_down` mode.
- [ ] 2.2 Описать schema-driven нормализацию внешних реестров через `Pool Schema Templates` и подготовить расширение под future integration adapters.
- [ ] 2.3 Описать contract для sale batch intake на leaf-узлах без line-level pairing с исходными receipt rows.

## 3. Factual Balance Projection
- [ ] 3.1 Спроектировать materialized read model по измерениям `pool / organization / edge / quarter / batch`.
- [ ] 3.2 Зафиксировать денежные меры `amount_with_vat`, `amount_without_vat`, `vat_amount`, а также derived counters `incoming`, `outgoing`, `open_balance`.
- [ ] 3.3 Спроектировать minute-scale direct-read sync path из бухгалтерских источников отчёта `Продажи` с bounded запросами, freshness metadata и обработкой maintenance / blocked external sessions без extension/change-log в v1.
- [ ] 3.4 Спроектировать carry-forward contract для незакрытого остатка на том же узле в следующий квартал.
- [ ] 3.5 Зафиксировать supported factual read boundary: только published 1C integration surfaces (standard OData entities/functions/virtual tables или explicit HTTP service), без direct DB access как primary production path.
- [ ] 3.6 Спроектировать deterministic attribution rule для leaf-scoped `sale`, чтобы `edge`-измерение projection оставалось согласованным без line-level pairing.

## 4. Operator Surfaces
- [ ] 4.1 Спроектировать summary/drill-down UI для factual balance без перегруженного diagnostic шума.
- [ ] 4.2 Добавить явную связь `run report -> batch settlement -> factual balance dashboard`.
- [ ] 4.3 Спроектировать operator-facing boundary так, чтобы run-local execution canvas не смешивал primary controls factual monitoring и manual review.
- [ ] 4.4 Спроектировать операторскую очередь manual review для `unattributed` документов и поздних корректировок, включая lifecycle review item и допустимые operator actions `attribute`, `reconcile`, `resolve_without_change`.

## 5. Verification
- [ ] 5.1 Добавить backend tests на batch intake, batch/run provenance, batch-backed idempotency, projection aggregation, carry-forward, parsing `CCPOOL` comment marker и `unattributed` / `late correction` queue.
- [ ] 5.2 Добавить frontend tests на batch-backed create-run UX, factual summary/drill-down и batch settlement statuses.
- [ ] 5.3 Подготовить live/dev verification сценарий `receipt batch -> distribution -> factual projection -> sale batch/manual sale capture -> refreshed summary -> manual reconcile late correction`.

## 6. Rollout / Operations
- [ ] 6.1 Зафиксировать source profile factual sync по данным отчёта `Продажи`: bounded reads из `РегистрБухгалтерии.Хозрасчетный.Обороты`, `РегистрСведений.ДанныеПервичныхДокументов` и связанных документов через published 1C integration surfaces.
- [ ] 6.2 Зафиксировать grammar `CCPOOL:v=1;...` и policy `pool`-based attribution для случаев, когда одна организация участвует в нескольких пулах одного квартала.
- [ ] 6.3 Подготовить rollout envelope для 700 ИБ: separate read/write workers, per-IB cap `1`, per-cluster cap `2`, global read cap `8`, polling tiers `120 сек / 10 мин / 60 мин`, отдельный ночной reconcile для закрытых кварталов.
- [ ] 6.4 Зафиксировать KPI telemetry и actionable alerts для freshness lag, read backlog, unattributed volume и late-correction queue перед rollout на 700 ИБ.
