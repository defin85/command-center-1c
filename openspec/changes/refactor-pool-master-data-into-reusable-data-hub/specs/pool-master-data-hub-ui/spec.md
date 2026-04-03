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

### Requirement: `/pools/master-data` MUST расширять canonical platform workspace shell
Система ДОЛЖНА (SHALL) реализовать `/pools/master-data` как расширение canonical platform workspace shell для Pools surfaces, используя route-level foundation, совместимый с project platform primitives, а не отдельный ad hoc page shell.

Система НЕ ДОЛЖНА (SHALL NOT) вводить второй competing route foundation на raw `Card + Tabs` или другой standalone page composition, если canonical workspace shell уже определён для этого surface.

Этот change ДОЛЖЕН (SHALL) ограничивать свою UI-работу добавлением новых зон, форм, detail/list surfaces и API wiring внутри canonical shell, а не повторным проектированием базовой route-level layout foundation.
Preparatory compatibility wrappers МОГУТ (MAY) существовать временно, но НЕ ДОЛЖНЫ (SHALL NOT) считаться выполнением этого требования или оправданием для shipping competing route foundation.

#### Scenario: Расширение master-data workspace не fork'ает platform migration
- **GIVEN** для `/pools/master-data` существует canonical platform workspace shell
- **WHEN** команда добавляет зоны `GLAccount`, `GLAccountSet`, `Bindings` и `Bootstrap Import`
- **THEN** route-level foundation переиспользуется из canonical shell
- **AND** change не создаёт второй параллельный layout migration для того же route

### Requirement: Workspace MUST показывать compatibility markers и revision semantics для reusable accounts
Система ДОЛЖНА (SHALL) отображать для `GLAccount` и `GLAccountSet` operator-facing сведения о compatibility scope и revision state, достаточные для безопасного выбора профиля в publication/factual contexts.

Система ДОЛЖНА (SHALL) различать как минимум:
- current draft state;
- target business/configuration compatibility markers;
- pinned metadata/published-surface admission evidence для target infobase;
- latest revision;
- pinned runtime revision, если профиль уже используется в readiness/checkpoint/execution context.

#### Scenario: Оператор видит, что latest revision не совпадает с pinned runtime revision
- **GIVEN** `GLAccountSet` уже используется в factual runtime context
- **AND** позже опубликована новая revision того же профиля
- **WHEN** оператор открывает detail `GLAccountSet`
- **THEN** UI явно показывает latest revision и pinned runtime revision как разные состояния
- **AND** оператор не воспринимает latest revision как уже автоматически применённую к historical runtime contexts

#### Scenario: Оператор редактирует draft и публикует новую revision
- **GIVEN** у `GLAccountSet` уже существует published revision
- **WHEN** оператор меняет состав draft через `upsert` и затем выполняет `publish`
- **THEN** UI показывает draft отдельно от latest published revision
- **AND** после `publish` появляется новая immutable revision
- **AND** ранее pinned runtime revision остаётся явно видимой как отдельное состояние

### Requirement: Workspace MUST отражать capability-gated sync semantics для reusable account entities
Система ДОЛЖНА (SHALL) строить operator-facing sync affordances для `GLAccount` и `GLAccountSet` из того же executable reusable-data capability contract, который используется backend runtime.
Этот capability contract ДОЛЖЕН (SHALL) поступать в frontend через generated shared contract/schema, а не через handwritten локальный registry.

Для этого change:
- `GLAccount` МОЖЕТ (MAY) отображаться в sync-oriented surface только как `bootstrap-only` / `unsupported-by-design` для outbound и bidirectional directions;
- `GLAccountSet` НЕ ДОЛЖЕН (SHALL NOT) получать direct mutating sync actions и МОЖЕТ (MAY) быть скрыт из mutation-oriented sync list или показан как non-actionable profile state;
- generic `Sync` zone НЕ ДОЛЖНА (SHALL NOT) создавать impression, что `GLAccount` или `GLAccountSet` поддерживают direct `CC -> ИБ` mutation в рамках этого change.

#### Scenario: Sync zone не предлагает мутации для account entities, где capability их запрещает
- **GIVEN** оператор открывает `/pools/master-data` и зону, связанную с sync/governance
- **WHEN** UI строит доступные действия для `GLAccount` и `GLAccountSet`
- **THEN** `GLAccount` не получает generic outbound/bidirectional mutate action
- **AND** `GLAccountSet` не отображается как mutating sync entity
- **AND** оператор видит явное non-actionable состояние вместо ложного универсального `Sync`

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
с операциями list/get/upsert для profile-level groups.

Для `gl-account-sets` profile surface ДОЛЖЕН (SHALL) поддерживать:
- `list/get/upsert` для profile и current draft;
- `publish` для создания immutable revision;
- `revisions list/get` для audit, readiness и runtime pinning UX.

#### Scenario: Workspace использует canonical namespace reusable-data endpoint-ов
- **GIVEN** оператор открывает tab `GLAccount` в `/pools/master-data`
- **WHEN** UI запрашивает список canonical `GLAccount`
- **THEN** запрос выполняется в namespace `/api/v2/pools/master-data/gl-accounts/`
- **AND** для create/edit используется `.../gl-accounts/upsert/`

#### Scenario: Workspace публикует GLAccountSet как новую revision, а не мутирует published state
- **GIVEN** оператор открыл detail `GLAccountSet`
- **WHEN** он сохраняет изменения draft и затем вызывает `publish`
- **THEN** UI использует profile-level `upsert` для draft state и отдельный `publish` endpoint для immutable revision
- **AND** published revision не редактируется через generic `upsert`

### Requirement: Workspace MUST поддерживать role-specific, owner-scoped и account-scoped bindings
Система ДОЛЖНА (SHALL) предоставлять в зоне `Bindings` явное управление type-specific scope-ключами binding:
- для `Party`: `(canonical_id, entity_type, database_id, ib_catalog_kind)`;
- для `Contract`: `(canonical_id, entity_type, database_id, owner_counterparty_id)`;
- для `Item/TaxProfile`: `(canonical_id, entity_type, database_id)`;
- для `GLAccount`: `(canonical_id, entity_type, database_id, chart_identity)`.

Система ДОЛЖНА (SHALL) отображать machine-readable конфликтные ответы backend без потери введённых оператором данных.
`chart_identity` ДОЛЖЕН (SHALL) быть отдельным operator-facing полем формы и списка bindings, а не скрытым metadata-only значением.

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
