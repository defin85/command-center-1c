## MODIFIED Requirements

### Requirement: Factual balance projection MUST использовать реальные документы и регистры ИБ как source of truth

Система ДОЛЖНА (SHALL) строить factual balance projection по реальным документам и регистрам ИБ, а не по ожидаемым суммам из runtime distribution artifacts.

Система ДОЛЖНА (SHALL) моделировать бухгалтерский эталон как versioned factual `source_profile`. Historical `sales_report_v1` ДОЛЖЕН (SHALL) оставаться replay-safe narrow profile, а расширение до parity с реальной семантикой отчёта `Продажи` ДОЛЖНО (SHALL) поставляться как новый explicit profile (`sales_report_v2` или более поздний successor), а не через silent widening `sales_report_v1`.

Для profile, выровненного с отчётом `Продажи`, система ДОЛЖНА (SHALL) покрывать те же bounded semantic branches, что и реальный отчёт:
- оптовую/выручечную ветку;
- розничную ветку;
- attribution `по оплате`;
- offsets по подарочным сертификатам;
- корректировки и их lineage к реализации/возврату.

Как минимум такой profile ДОЛЖЕН (SHALL) валидировать и использовать published surfaces, эквивалентные:
- `РегистрБухгалтерии.Хозрасчетный.Обороты(...)`;
- `РегистрСведений.ДанныеПервичныхДокументов`;
- документам `РеализацияТоваровУслуг`, `ВозвратТоваровОтПокупателя`, `КорректировкаРеализации`, `ОтчетОРозничныхПродажах`;
- supporting published lookup surface с семантикой `ВидыОплатОрганизаций`, достаточной для payment/certificate classification.

Projection ДОЛЖЕН (SHALL) хранить как минимум три денежные меры:
- `amount_with_vat`
- `amount_without_vat`
- `vat_amount`

Projection ДОЛЖЕН (SHALL) учитывать как документы, созданные Command Center, так и ручные документы пользователя, если они влияют на фактический баланс и доступны для чтения из ИБ.

Primary sync path НЕ ДОЛЖЕН (SHALL NOT) выполнять unbounded full scan всего бухгалтерского регистра; worker sync ДОЛЖЕН (SHALL) ограничивать чтение организациями пула, кварталом, выбранным `source_profile`, branch-scoped account families и типами движений, используемыми отчётом `Продажи`.

Bounded account subset ДОЛЖЕН (SHALL) резолвиться через first-class quarter-scoped factual scope selection, keyed by `pool + source_profile + quarter_start`, которая pin-ит одну published revision canonical `GLAccountSet` и её member `GLAccount` bindings, а не через hardcoded account codes в runtime defaults. Для parity profile этот scope ДОЛЖЕН (SHALL) различать account families, соответствующие semantics отчёта `Продажи`: выручка, денежные средства, расчёты с контрагентами, розничные расчёты и корректировки.

Live lookup target chart-of-accounts ДОЛЖЕН (SHALL) использоваться только в readiness/preflight path для materialize или verify `resolved_bindings` snapshot выбранной pinned revision. Worker execution и replay artifact с `factual_scope_contract.v2` НЕ ДОЛЖНЫ (SHALL NOT) silently подменять этот snapshot latest live lookup.

Primary production read path ДОЛЖЕН (SHALL) использовать только поддерживаемые published integration surfaces 1С: standard OData entities/functions/virtual tables или явный published HTTP service contract. Система НЕ ДОЛЖНА (SHALL NOT) использовать прямой доступ к таблицам БД ИБ как основной путь factual sync в production.

#### Scenario: Readiness блокирует parity profile при неполной публикации retail/payment surfaces
- **GIVEN** для выбранного parity profile опубликованы `Хозрасчетный.Обороты`, `ДанныеПервичныхДокументов` и оптовые документы
- **AND** отсутствует хотя бы одна required surface для розничной или payment/certificate semantics, например `ОтчетОРозничныхПродажах` или published lookup с семантикой `ВидыОплатОрганизаций`
- **WHEN** factual preflight или default workspace sync проверяет readiness
- **THEN** система завершает проверку fail-closed с machine-readable blocker по отсутствующей surface
- **AND** не enqueue'ит partial sync, который silently деградирует semantics отчёта `Продажи`

#### Scenario: Worker читает bounded payment и certificate slices без unbounded scan
- **GIVEN** для пула известны организации, квартал и pinned revision selected `GLAccountSet`, соответствующий parity profile отчёта `Продажи`
- **WHEN** `read worker` обновляет factual projection
- **THEN** он читает только те branch-scoped account families и движения, которые объявлены выбранным `source_profile`
- **AND** включает payment/certificate semantics без full scan всего `Хозрасчетный`
- **AND** не использует hardcoded runtime constants как source-of-truth для bounded account scope

#### Scenario: Workspace, scheduler и preflight используют один selector для того же квартала
- **GIVEN** workspace default sync, scheduler и preflight работают с одним `pool + source_profile + quarter_start`
- **WHEN** каждый из них резолвит bounded factual account scope
- **THEN** все они используют один и тот же quarter-scoped factual scope selection record
- **AND** фиксируют одну и ту же published `GLAccountSet` revision до явного repin

## ADDED Requirements

### Requirement: Sales-report parity rollout MUST хранить source profile lineage явным и replay-safe

Система ДОЛЖНА (SHALL) трактовать расширение semantics отчёта `Продажи` как новый factual `source_profile` lineage, а не как in-place mutation существующего lineage.

Для этого система ДОЛЖНА (SHALL):
- сохранять `sales_report_v1` checkpoints, selector keys, scope fingerprints и historical projections replay-safe и неизменными;
- создавать отдельные selector keys, scope fingerprints, checkpoints и inspect lineage для parity profile (`sales_report_v2` или successor) даже для того же `pool + quarter`;
- показывать active `source_profile` в machine-readable checkpoint/workflow metadata и operator-facing inspect/workspace surface в bridge period;
- позволять controlled side-by-side validation и cutover без переписывания existing `sales_report_v1` totals.

Система НЕ ДОЛЖНА (SHALL NOT) silently подменять existing factual lineage новым parity profile только потому, что для того же `pool + quarter` стал доступен более широкий source profile.

#### Scenario: Один и тот же quarter имеет разные lineages для v1 и parity profile
- **GIVEN** для `pool + quarter` уже существует factual checkpoint с `source_profile=sales_report_v1`
- **WHEN** оператор или runtime запускает sync для parity profile того же `pool + quarter`
- **THEN** система создаёт другой selector key и другой `scope_fingerprint`
- **AND** historical `sales_report_v1` checkpoint остаётся replay-safe и inspectable как отдельный lineage
- **AND** новый parity path не маскируется под retry существующего `v1` checkpoint

#### Scenario: Operator surface явно показывает active source profile в bridge period
- **GIVEN** для одного и того же `pool + quarter` доступны результаты narrow `sales_report_v1` и parity profile
- **WHEN** оператор открывает factual workspace или inspect surface
- **THEN** UI и machine-readable payload явно показывают, какой `source_profile` построил текущий summary/drill-down
- **AND** оператор может отличить bridge-parity results от historical `sales_report_v1`
