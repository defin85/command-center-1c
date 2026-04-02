## MODIFIED Requirements

### Requirement: Pools MUST предоставлять отдельный master-data workspace для оператора
Система ДОЛЖНА (SHALL) предоставлять отдельную страницу `/pools/master-data` как рабочее пространство для управления каноническими reusable-data сущностями в tenant scope.

Система ДОЛЖНА (SHALL) поддерживать в workspace минимум семь рабочих зон:
- `Party`;
- `Item`;
- `Contract`;
- `TaxProfile`;
- `GLAccount`;
- `GLAccountSet`;
- `Bindings`.

Workspace ДОЛЖЕН (SHALL) быть доступен из основного меню Pools и работать в рамках текущего tenant context.

#### Scenario: Оператор открывает reusable-data workspace из меню Pools
- **GIVEN** пользователь имеет доступ к Pools и выбран tenant context
- **WHEN** пользователь открывает `/pools/master-data`
- **THEN** система отображает рабочие зоны `Party`, `Item`, `Contract`, `TaxProfile`, `GLAccount`, `GLAccountSet`, `Bindings`
- **AND** операции выполняются в tenant scope без cross-tenant данных

### Requirement: Workspace MUST показывать compatibility markers и revision semantics для reusable accounts
Система ДОЛЖНА (SHALL) отображать для `GLAccount` и `GLAccountSet` operator-facing сведения о compatibility scope и revision state, достаточные для безопасного выбора профиля в publication/factual contexts.

Система ДОЛЖНА (SHALL) различать как минимум:
- target business/configuration compatibility markers;
- latest revision;
- pinned runtime revision, если профиль уже используется в readiness/checkpoint/execution context.

#### Scenario: Оператор видит, что latest revision не совпадает с pinned runtime revision
- **GIVEN** `GLAccountSet` уже используется в factual runtime context
- **AND** позже опубликована новая revision того же профиля
- **WHEN** оператор открывает detail `GLAccountSet`
- **THEN** UI явно показывает latest revision и pinned runtime revision как разные состояния
- **AND** оператор не воспринимает latest revision как уже автоматически применённую к historical runtime contexts

### Requirement: Master-data API MUST использовать Problem Details контракт для ошибок
Система ДОЛЖНА (SHALL) возвращать ошибки reusable-data workspace endpoint-ов в формате `application/problem+json`.

Problem payload ДОЛЖЕН (SHALL) включать поля `type`, `title`, `status`, `detail`, `code`.

Система ДОЛЖНА (SHALL) публиковать endpoint-ы workspace в namespace `/api/v2/pools/master-data/` для групп:
- `parties`,
- `items`,
- `contracts`,
- `tax-profiles`,
- `gl-accounts`,
- `gl-account-sets`,
- `bindings`,
с операциями list/get/upsert для каждой группы.

#### Scenario: Workspace использует canonical namespace reusable-data endpoint-ов
- **GIVEN** оператор открывает tab `GLAccount` в `/pools/master-data`
- **WHEN** UI запрашивает список canonical `GLAccount`
- **THEN** запрос выполняется в namespace `/api/v2/pools/master-data/gl-accounts/`
- **AND** для create/edit используется `.../gl-accounts/upsert/`

### Requirement: Workspace MUST поддерживать role-specific, owner-scoped и account-scoped bindings
Система ДОЛЖНА (SHALL) предоставлять в зоне `Bindings` явное управление type-specific scope-ключами binding:
- для `Party`: `(canonical_id, entity_type, database_id, ib_catalog_kind)`;
- для `Contract`: `(canonical_id, entity_type, database_id, owner_counterparty_id)`;
- для `Item/TaxProfile`: `(canonical_id, entity_type, database_id)`;
- для `GLAccount`: `(canonical_id, entity_type, database_id, chart_identity)`.

Система ДОЛЖНА (SHALL) отображать machine-readable конфликтные ответы backend без потери введённых оператором данных.

#### Scenario: Оператор настраивает GLAccount binding для target chart
- **GIVEN** оператор открыл зону `Bindings`
- **WHEN** он создаёт binding для `GLAccount` и указывает target database и chart identity
- **THEN** система сохраняет deterministic account binding scope
- **AND** повторное создание того же scope приводит к operator-friendly conflict, а не к silent duplicate

### Requirement: Document policy authoring MUST поддерживать guided master-data token picker
Система ДОЛЖНА (SHALL) в `/pools/catalog` предоставлять guided token picker для `field_mapping` и `table_parts_mapping` в `document_policy` builder.

Token picker ДОЛЖЕН (SHALL) генерировать токены совместимого формата:
- `master_data.party.<canonical_id>.<organization|counterparty>.ref`;
- `master_data.item.<canonical_id>.ref`;
- `master_data.contract.<canonical_id>.<owner_counterparty_canonical_id>.ref`;
- `master_data.tax_profile.<canonical_id>.ref`;
- `master_data.gl_account.<canonical_id>.ref`.

#### Scenario: Оператор выбирает GLAccount через token picker
- **GIVEN** оператор редактирует account field в `field_mapping` или `table_parts_mapping`
- **WHEN** он выбирает `GLAccount` в token picker
- **THEN** система подставляет валидный token `master_data.gl_account.<canonical_id>.ref`
- **AND** оператору не требуется ручной ввод token строки

### Requirement: Pool master-data workspace MUST предоставлять операторский Bootstrap Import from IB wizard
Система ДОЛЖНА (SHALL) в `/pools/master-data` предоставить отдельную рабочую зону `Bootstrap Import` для первичного импорта canonical reusable-data из выбранной ИБ.

Wizard ДОЛЖЕН (SHALL) как минимум поддерживать шаги:
1. выбор базы и entity scope;
2. preflight;
3. dry-run summary;
4. execute.

Wizard ДОЛЖЕН (SHALL) поддерживать как минимум import scope для `Party`, `Item`, `TaxProfile`, `Contract`, `GLAccount`.

#### Scenario: Оператор запускает bootstrap wizard для GLAccount
- **GIVEN** пользователь открыл `/pools/master-data` в активном tenant context
- **WHEN** он выбирает в `Bootstrap Import` entity scope `GLAccount`
- **THEN** система отображает тот же staged wizard lifecycle без отдельного account-only flow
- **AND** запуск выполняется через канонический v2 API bootstrap import

#### Scenario: UI не предлагает bootstrap import для GLAccountSet
- **GIVEN** оператор открыл `Bootstrap Import` wizard
- **WHEN** он выбирает entity scope для импорта
- **THEN** `GLAccountSet` отсутствует среди importable entity types
- **AND** UI не создает ложное ожидание, что grouped profile materialize'ится напрямую из target ИБ
