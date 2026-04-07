## 1. Source profile и published boundary

- [ ] 1.1 Ввести versioned factual source profile для parity с отчётом `Продажи` и зафиксировать, что historical `sales_report_v1` остаётся replay-safe и не расширяется silently.
- [ ] 1.2 Описать и реализовать branch-scoped semantics parity profile: оптовая/выручечная ветка, розница, `по оплате`, подарочные сертификаты и корректировки. (после 1.1)
- [ ] 1.3 Расширить published metadata validation, factual read boundary и readiness/preflight до required surfaces parity profile, включая `ОтчетОРозничныхПродажах` и supporting published lookup surface с семантикой `ВидыОплатОрганизаций`, с fail-closed blockers при неполной публикации. (после 1.2)

## 2. Scope selection, runtime и rollout

- [ ] 2.1 Расширить quarter-scoped factual scope selection и workflow contract до branch-scoped account families, соответствующих semantics отчёта `Продажи`: выручка, денежные средства, расчёты с контрагентами, розничные расчёты и корректировки.
- [ ] 2.2 Обновить orchestrator/worker factual sync path так, чтобы parity profile читал bounded slices для розницы, `по оплате`, сертификатов и корректировок без unbounded full scan. (после 2.1)
- [ ] 2.3 Обеспечить bridge/cutover path между `sales_report_v1` и parity profile: отдельные selector keys, checkpoints, scope fingerprints и operator-visible source profile provenance для одного и того же `pool + quarter`. (после 2.1; можно параллельно с 2.2)

## 3. Operator/API surface и evidence

- [ ] 3.1 Обновить inspect/workspace/API surfaces так, чтобы active `source_profile` и bridge provenance были видны оператору и не маскировались под один lineage. (после 2.3)
- [ ] 3.2 Добавить automated tests для source-profile validation, readiness blockers, scope lineage split `v1` vs parity profile и workflow/worker contracts.
- [ ] 3.3 Добавить acceptance evidence на representative semantics отчёта `Продажи`: опт, розница, `по оплате`, подарочные сертификаты и корректировки. (после 2.2)

## 4. Verification

- [ ] 4.1 Прогнать релевантные backend tests для factual source profile, preflight, scope selection, sync runtime и workspace/API surfaces.
- [ ] 4.2 Прогнать релевантные worker tests для factual transport/contract wiring.
- [ ] 4.3 Прогнать релевантные frontend/API tests, если operator-facing source profile/provenance surface меняется.
- [ ] 4.4 Прогнать `openspec validate update-pool-factual-monitoring-sales-report-parity --strict --no-interactive`.
