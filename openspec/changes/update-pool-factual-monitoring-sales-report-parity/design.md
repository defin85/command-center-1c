## Context

Текущий factual monitoring уже использует versioned `source_profile`, quarter-scoped selector keys и pinned runtime artifacts. В shipped коде и спеках это выражено как `sales_report_v1`, который:
- валидирует только `Хозрасчетный`, `ДанныеПервичныхДокументов` и три документа оптовой реализации/возврата/корректировки;
- резолвит один узкий bounded account subset;
- не моделирует розницу, `по оплате`, сертификатные offsets и supporting lookup semantics реального отчёта `Продажи`.

Разбор checked-in 1С-отчёта `Продажи` показывает, что он использует более широкую доменную семантику:
- `РегистрБухгалтерии.Хозрасчетный.Обороты(...)` как общий бухгалтерский источник;
- `РегистрСведений.ДанныеПервичныхДокументов` как secondary source первички;
- документы `РеализацияТоваровУслуг`, `ВозвратТоваровОтПокупателя`, `КорректировкаРеализации`, `ОтчетОРозничныхПродажах`;
- supporting lookups с семантикой `ВидыОплатОрганизаций` для сертификатных договоров;
- отдельные account families для выручки, денежных средств, расчётов с контрагентами, розничных расчётов и корректировок.

Если silently расширить `sales_report_v1`, мы потеряем replay-safety: historical checkpoints, selector keys и workflow contracts уже используют `source_profile` как часть lineage.

## Goals / Non-Goals

- Goals:
  - выровнять factual source semantics с реальным отчётом `Продажи`, а не с его урезанным подмножеством;
  - сохранить bounded read discipline и запрет на direct DB access/full scan;
  - доставить parity как versioned, replay-safe rollout, а не как silent mutation `sales_report_v1`;
  - дать оператору и runtime явную provenance-информацию о том, какой source profile построил текущую projection.
- Non-Goals:
  - не превращать 1С-отчёт `Продажи` в synchronous runtime dependency;
  - не делать generic query engine для всех бухгалтерских отчётов;
  - не переписывать UI factual workspace шире, чем требуется для source profile provenance и bridge visibility.

## Decisions

### 1. Parity поставляется как новый versioned source profile, а не как расширение `sales_report_v1`

Любое существенное расширение бухгалтерской семантики меняет bounded read contract, состав required metadata surfaces и selector lineage. Поэтому parity с реальным отчётом `Продажи` должна поставляться как `sales_report_v2` (или другой explicit successor), а `sales_report_v1` должен оставаться frozen для historical replay, checkpoint inspection и rollback.

### 2. Source profile становится branch-aware

Новый parity profile должен описывать не просто "список required entities", а bounded semantic branches:
- `revenue_turnover`
- `retail_turnover`
- `payment_attribution`
- `gift_certificate_offsets`
- `correction_lineage`

Для каждой ветки contract должен фиксировать:
- required published surfaces;
- account families / movement filters;
- правила attribution/provenance;
- вклад ветки в projection/reconcile semantics.

### 3. Read boundary и readiness становятся profile-driven

Текущий static allowlist в `factual_source_profile.py` и `factual_read_boundary.py` недостаточен для parity rollout. Boundary/preflight должны валидировать surfaces по выбранному source profile, а не по hardcoded `v1` списку.

Если часть needed semantics недоступна через standard OData entity/function surface, допускается explicit published HTTP service contract, но только как first-class declared branch dependency с теми же fail-closed readiness rules. Silent fallback на "посчитать как получится" недопустим.

### 4. Account scope расширяется до branch-scoped families, но остаётся bounded

Parity с отчётом `Продажи` требует не одного набора "счетов выручки", а нескольких account families, соответствующих логике отчёта:
- выручка;
- денежные средства;
- расчёты с контрагентами;
- розничные расчёты;
- корректировки.

Эти families должны по-прежнему резолвиться через canonical quarter-scoped selection/bindings и попадать в workflow contract как machine-readable scope contract, без hardcoded ad hoc defaults в worker execution.

### 5. Rollout проходит через bridge period с явной provenance

До default cutover parity profile должен уметь существовать рядом с `sales_report_v1` для того же `pool + quarter`. Для этого нужны:
- разные selector keys и scope fingerprints;
- разные checkpoints/projections или иная явная lineage separation;
- operator-visible indication active `source_profile`;
- возможность сравнить `v1` и parity profile на representative наборах данных до default rollout.

## Risks / Trade-offs

- Parity с отчётом `Продажи` увеличит сложность factual source profile и preflight.
  - Mitigation: branch-aware contract и explicit fail-closed blockers вместо implicit runtime heuristics.
- Не все target ИБ могут публиковать supporting surfaces в одинаковом виде.
  - Mitigation: допустить explicit published HTTP service contract только как declared dependency с тем же readiness contract.
- Bridge period добавляет operator-facing сложность, потому что для одного quarter могут существовать два lineages.
  - Mitigation: показывать active `source_profile` явно и не смешивать `v1` и parity totals под одним checkpoint lineage.

## Migration Plan

1. Ввести parity source profile и profile-driven metadata validation/read boundary.
2. Расширить scope selection и workflow contract до branch-scoped account families.
3. Запустить bridge period с explicit lineage split `sales_report_v1` vs parity profile.
4. Накопить automated parity evidence на representative сценариях отчёта `Продажи`.
5. Только после этого переключать default factual source profile для новых sync path.
