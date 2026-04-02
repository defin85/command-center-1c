## MODIFIED Requirements

### Requirement: Factual balance projection MUST использовать реальные документы и регистры ИБ как source of truth
Система ДОЛЖНА (SHALL) строить factual balance projection по реальным документам и регистрам ИБ, а не по ожидаемым суммам из runtime distribution artifacts.

В первой итерации бухгалтерским эталоном ДОЛЖЕН (SHALL) считаться отчёт `Продажи`, построенный на bounded чтении `РегистрБухгалтерии.Хозрасчетный.Обороты(...)`, `РегистрСведений.ДанныеПервичныхДокументов` и связанных документов `РеализацияТоваровУслуг`, `ВозвратТоваровОтПокупателя`, `КорректировкаРеализации`.

Projection ДОЛЖЕН (SHALL) хранить как минимум три денежные меры:
- `amount_with_vat`
- `amount_without_vat`
- `vat_amount`

Projection ДОЛЖЕН (SHALL) учитывать как документы, созданные Command Center, так и ручные документы пользователя, если они влияют на фактический баланс и доступны для чтения из ИБ.

Primary sync path НЕ ДОЛЖЕН (SHALL NOT) выполнять unbounded full scan всего бухгалтерского регистра; worker sync ДОЛЖЕН (SHALL) ограничивать чтение организациями пула, кварталом и счетами/типами движений, используемыми отчётом `Продажи`.

Bounded account subset ДОЛЖЕН (SHALL) резолвиться через pinned revision canonical reusable-data `GLAccountSet` и member `GLAccount` bindings, а не через hardcoded account codes в runtime defaults.

Primary production read path ДОЛЖЕН (SHALL) использовать только поддерживаемые published integration surfaces 1С: standard OData entities/functions/virtual tables или явный published HTTP service contract. Система НЕ ДОЛЖНА (SHALL NOT) использовать прямой доступ к таблицам БД ИБ как основной путь factual sync в production.

#### Scenario: Worker sync читает bounded slice через canonical GLAccountSet
- **GIVEN** для пула известны организации, квартал и pinned revision selected `GLAccountSet`, соответствующий отчёту `Продажи`
- **WHEN** `read worker` обновляет factual projection
- **THEN** он резолвит target account refs через member `GLAccount` bindings этого набора
- **AND** не использует hardcoded runtime constants как source-of-truth для bounded account scope

## ADDED Requirements

### Requirement: Factual preflight MUST fail-closed на incomplete reusable account coverage до worker execution
Система ДОЛЖНА (SHALL) до старта factual worker execution проверять coverage selected `GLAccountSet` по каждой target ИБ и возвращать machine-readable blocker, если хотя бы один required account не имеет валидного binding в target chart of accounts.

Система НЕ ДОЛЖНА (SHALL NOT) откладывать такую несовместимость до глубокой OData ошибки внутри running worker, если её можно детерминированно обнаружить в preflight/readiness path.

#### Scenario: Missing member binding блокирует factual sync до enqueue
- **GIVEN** selected `GLAccountSet` содержит canonical account, отсутствующий в binding coverage для target ИБ
- **WHEN** factual preflight или default workspace sync проверяет readiness
- **THEN** система завершает проверку fail-closed с machine-readable blocker по `gl_account`
- **AND** factual workflow execution не enqueue'ится

### Requirement: Factual runtime artifacts MUST pin `GLAccountSet` revision
Система ДОЛЖНА (SHALL) сохранять в factual preflight results, checkpoints и связанных runtime artifacts идентификатор pinned `GLAccountSet` revision и effective member snapshot, использованные для bounded account scope.

Система НЕ ДОЛЖНА (SHALL NOT) silently пересчитывать historical readiness или replay на latest revision profile, если runtime context уже был создан под предыдущую revision.

#### Scenario: Поздняя правка account set не меняет historical factual checkpoint scope
- **GIVEN** factual checkpoint уже создан с pinned `GLAccountSet` revision
- **WHEN** оператор публикует новую revision того же account set
- **THEN** существующий checkpoint сохраняет ранее pinned revision и effective members
- **AND** historical quarter scope не меняется автоматически только из-за новой latest revision
