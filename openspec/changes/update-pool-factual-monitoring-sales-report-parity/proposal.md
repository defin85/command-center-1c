# Change: Довести factual monitoring до parity с реальной семантикой отчёта `Продажи`

## Почему
Текущий factual monitoring уже заявляет отчёт `Продажи` бухгалтерским эталоном, но shipped `sales_report_v1` покрывает только узкое ядро этого отчёта: `Хозрасчетный.Обороты`, `ДанныеПервичныхДокументов` и три документа по оптовой реализации/возврату/корректировке.

Реальный отчёт `Продажи` в 1С использует более широкую семантику: розничную ветку, ветку `по оплате`, логику подарочных сертификатов, `ОтчетОРозничныхПродажах`, supporting lookups для сертификатных договоров и отдельные account families для выручки, денежных средств, расчётов с контрагентами, розничных расчётов и корректировок. Пока этот разрыв не описан как first-class contract, оператор может сравнивать centralized factual summary с отчётом `Продажи` и видеть необъяснимые расхождения.

Расширять этот scope внутри `sales_report_v1` нельзя: `source_profile` уже зашит в quarter-scoped selector keys, checkpoints, workflow contracts и historical replay artifacts. Тихое расширение `v1` сломает replay-safety и трассируемость.

## Что меняется
- Вводится versioned sales-report parity profile для factual sync (`sales_report_v2` или эквивалентный explicit successor), который покрывает bounded semantics отчёта `Продажи`: оптовую/выручечную ветку, розницу, `по оплате`, подарочные сертификаты и корректировки.
- Published factual read boundary и readiness/preflight расширяются до required surfaces, нужных для этих веток: `Хозрасчетный.Обороты`, `ДанныеПервичныхДокументов`, документы `РеализацияТоваровУслуг`, `ВозвратТоваровОтПокупателя`, `КорректировкаРеализации`, `ОтчетОРозничныхПродажах` и supporting published lookup surface с семантикой `ВидыОплатОрганизаций` для payment/certificate classification.
- Quarter-scoped factual scope selection и workflow contract расширяются от одного узкого account subset до branch-scoped account families, соответствующих логике отчёта `Продажи`: выручка, денежные средства, расчёты с контрагентами, розничные расчёты и корректировки.
- Rollout оформляется как replay-safe bridge: historical `sales_report_v1` lineages остаются неизменными, а `sales_report_v2` получает отдельные selector keys, scope fingerprints, checkpoints и operator-visible provenance.
- Добавляется acceptance coverage, которая доказывает parity profile на representative сценариях `Продажи`: опт, розница, `по оплате`, подарочные сертификаты, корректировки.

## Impact
- Affected specs: `pool-factual-balance-monitoring`
- Affected code:
  - `orchestrator/apps/intercompany_pools/factual_source_profile.py`
  - `orchestrator/apps/intercompany_pools/factual_read_boundary.py`
  - `orchestrator/apps/intercompany_pools/factual_preflight.py`
  - `orchestrator/apps/intercompany_pools/factual_scope_selection.py`
  - `orchestrator/apps/intercompany_pools/factual_sync_runtime.py`
  - `orchestrator/apps/intercompany_pools/factual_workspace_runtime.py`
  - `orchestrator/apps/intercompany_pools/tests/test_factual_*`
  - `go-services/worker/internal/drivers/poolops/factual_transport.go`
  - `go-services/worker/internal/drivers/poolops/factual_transport_test.go`
  - `contracts/orchestrator/openapi.yaml`
  - factual workspace/API surfaces, если потребуется показать active source profile и bridge status
- Non-goals:
  - не переходить на direct DB access или unbounded full scan бухгалтерского регистра;
  - не переписывать сам отчёт `Продажи` в 1С и не делать его runtime dependency;
  - не перепроектировать batch settlement/review vocabulary вне того, что нужно для sales-report parity.
