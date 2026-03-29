## 0. Implementation Readiness Gate
- [x] 0.1 Зафиксировать implementation verdict `Ready with conditions` и подтвердить, что coding phase стартует только при сохранении варианта `B` внутри текущих `orchestrator + worker + frontend` boundaries.
- [x] 0.2 Заморозить public/domain contracts для `PoolBatch`, batch-backed `top_down`, factual read-model/API surface и grammar `CCPOOL:v=1;...` до старта runtime/UI реализации.
- [x] 0.3 Подтвердить на pilot/preflight cohort ИБ доступность published 1C integration surfaces для bounded factual sync без direct DB access как primary production path.
- [x] 0.4 Зафиксировать, что factual projection, batch settlement, checkpoints и review queue реализуются как отдельный `orchestrator`-owned boundary и не подменяют existing execution store `PoolRun`.
- [x] 0.5 Зафиксировать reuse existing worker scheduling/fairness primitives и rollout envelope для `read/reconcile` lanes вместо нового primary runtime path.
- [x] 0.6 Зафиксировать, что `/pools/runs` остаётся execution-centric surface, а factual monitoring/manual review выходят отдельным workspace с explicit linkage из run report.
- [x] 0.7 Зафиксировать, что новый factual workspace входит в UI governance perimeter и использует project UI platform layer; если route использует `MasterDetail`, он обязан соблюдать compact master-pane contract и mobile-safe fallback.

## 1. Domain Contracts
- [x] 1.1 Спроектировать canonical `PoolBatch` contract для `receipt` и `sale` intake, включая provenance, batch kind, source metadata, schema/integration references и правило `one batch = one pool_run`.
- [x] 1.2 Зафиксировать архитектурную границу варианта `B`: `orchestrator` владеет `PoolBatch`, batch settlement lifecycle, factual projection и review queue; новый top-level service или новый primary runtime не вводятся.
- [x] 1.3 Спроектировать отдельный batch settlement lifecycle/read-model, не меняя существующий `PoolRun.status`.
- [x] 1.4 Зафиксировать, что existing execution snapshots/read-models (`PoolRun`, `runtime_projection_snapshot`, `publication_summary`, `PoolPublicationAttempt`) не используются как factual source-of-truth.
- [x] 1.5 Зафиксировать batch-backed idempotency contract для `batch_id + start_organization_id + period + binding revision`, не ломая existing manual `top_down` path.
- [x] 1.6 Зафиксировать traceability contract для документов Command Center через machine-readable комментарий `CCPOOL:v=1;...`, включая policy для multi-pool attribution, stable retry/update semantics и отдельный contract для `unattributed` документов.
- [x] 1.7 Зафиксировать decomposition варианта `B` на три изолированные подсистемы `intake`, `factual read/projection`, `reconcile/review`, включая ownership, входы/выходы и запрещённые пересечения ответственности.

## 2. Batch Intake
- [x] 2.1 Описать API/UI контракт intake для batch-backed top-down запуска с явным выбором `pool`, `batch_id` и `start_organization`, сохранив existing manual `top_down` mode.
- [x] 2.2 Описать schema-driven нормализацию внешних реестров через `Pool Schema Templates` и подготовить расширение под future integration adapters.
- [x] 2.3 Описать contract для sale batch intake на leaf-узлах без line-level pairing с исходными receipt rows.
- [x] 2.4 Зафиксировать, что `intake subsystem` отвечает только за нормализацию, provenance и run kickoff, и не владеет factual projection, settlement summary или manual review state.

## 3. Factual Balance Projection
- [x] 3.1 Спроектировать materialized read model по измерениям `pool / organization / edge / quarter / batch` в `orchestrator`-owned persistence boundary, а не как переиспользование execution snapshots.
- [x] 3.2 Зафиксировать денежные меры `amount_with_vat`, `amount_without_vat`, `vat_amount`, а также derived counters `incoming`, `outgoing`, `open_balance`.
- [x] 3.3 Спроектировать minute-scale direct-read sync path из бухгалтерских источников отчёта `Продажи` с bounded запросами, freshness metadata и обработкой maintenance / blocked external sessions без extension/change-log в v1.
- [x] 3.4 Спроектировать carry-forward contract для незакрытого остатка на том же узле в следующий квартал.
- [x] 3.5 Зафиксировать supported factual read boundary: только published 1C integration surfaces (standard OData entities/functions/virtual tables или explicit HTTP service), без direct DB access как primary production path.
- [x] 3.6 Спроектировать deterministic attribution rule для leaf-scoped `sale`, чтобы `edge`-измерение projection оставалось согласованным без line-level pairing.
- [x] 3.7 Зафиксировать, что `factual read/projection subsystem` работает в отдельном `read` lane, materializes projection/checkpoints/settlement и не управляет create-run или operator review actions.

## 4. Operator Surfaces
- [x] 4.1 Спроектировать summary/drill-down UI для factual balance без перегруженного diagnostic шума как отдельный factual workspace/route внутри существующего frontend приложения.
- [x] 4.2 Добавить явную связь `run report -> batch settlement -> factual balance dashboard`.
- [x] 4.3 Спроектировать operator-facing boundary так, чтобы run-local execution canvas не смешивал primary controls factual monitoring и manual review.
- [x] 4.4 Спроектировать операторскую очередь manual review для `unattributed` документов и поздних корректировок, включая lifecycle review item и допустимые operator actions `attribute`, `reconcile`, `resolve_without_change`.
- [x] 4.5 Зафиксировать, что `reconcile/review subsystem` изолирован от `intake` и `run execution`: деградация review queue не должна менять `PoolRun.status` или batch intake contract.
- [x] 4.6 Собрать factual workspace через project UI platform layer; если route использует `MasterDetail`/catalog-detail shell, master pane должен оставаться compact selection surface без table-first composition и horizontal overflow как primary path.
- [x] 4.7 Спроектировать mobile-safe fallback для detail/review (`Drawer`, off-canvas panel или route/state fallback) без page-wide horizontal overflow.

## 5. Verification
- [x] 5.1 Добавить backend tests на batch intake, batch/run provenance, batch-backed idempotency, projection aggregation, carry-forward, parsing `CCPOOL` comment marker и `unattributed` / `late correction` queue.
- [x] 5.2 Добавить frontend tests на batch-backed create-run UX, factual summary/drill-down и batch settlement statuses.
- [x] 5.3 Подготовить live/dev verification сценарий `receipt batch -> distribution -> factual projection -> sale batch/manual sale capture -> refreshed summary -> manual reconcile late correction`.
- [x] 5.4 Добавить browser-level coverage для нового factual route на UI governance invariants: compact selection/detail split, отсутствие pane/page horizontal overflow и mobile fallback detail/review.
- [x] 5.5 Прогнать `cd frontend && npm run lint`, `cd frontend && npm run test:browser:ui-platform`, `cd frontend && npm run validate:ui-platform` как blocking UI validation gate для этого change.

## 6. Rollout / Operations
- [x] 6.1 Зафиксировать source profile factual sync по данным отчёта `Продажи`: bounded reads из `РегистрБухгалтерии.Хозрасчетный.Обороты`, `РегистрСведений.ДанныеПервичныхДокументов` и связанных документов через published 1C integration surfaces.
- [x] 6.2 Зафиксировать grammar `CCPOOL:v=1;...` и policy `pool`-based attribution для случаев, когда одна организация участвует в нескольких пулах одного квартала.
- [x] 6.3 Подготовить rollout envelope для 700 ИБ: separate read/write worker lanes внутри текущего worker runtime family, per-IB cap `1`, per-cluster cap `2`, global read cap `8`, polling tiers `120 сек / 10 мин / 60 мин`, отдельный ночной reconcile для закрытых кварталов.
- [x] 6.4 Зафиксировать KPI telemetry и actionable alerts для freshness lag, read backlog, unattributed volume и late-correction queue перед rollout на 700 ИБ.
- [x] 6.5 Зафиксировать failure-isolation policy между тремя подсистемами: backlog/staleness в `read/projection` и `reconcile/review` поднимают сигналы и алерты, но не выключают `intake` без явного operator decision.

## Evidence
- Pilot/preflight bundle: `artifacts/2026-03-29-pilot-preflight-evidence.json`
- Live default-path acceptance snapshot: `artifacts/2026-03-29-live-default-path-evidence.md`
