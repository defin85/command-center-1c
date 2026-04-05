## MODIFIED Requirements

### Requirement: Pools MUST предоставлять отдельный master-data workspace для оператора
Система ДОЛЖНА (SHALL) предоставлять отдельную страницу `/pools/master-data` как рабочее пространство для управления каноническими master-data и reusable account сущностями в tenant scope.

Система ДОЛЖНА (SHALL) поддерживать в workspace минимум следующие рабочие зоны:
- `Party`;
- `Item`;
- `Contract`;
- `TaxProfile`;
- `GLAccount`;
- `GLAccountSet`;
- `Bindings`;
- `Bootstrap Import`.

Workspace ДОЛЖЕН (SHALL) быть доступен из основного меню Pools, работать в рамках текущего tenant context и расширяться внутри canonical platform shell, а не через второй parallel page foundation.

#### Scenario: Оператор открывает reusable-account zones внутри master-data workspace
- **GIVEN** пользователь имеет доступ к Pools и выбран tenant context
- **WHEN** пользователь открывает `/pools/master-data`
- **THEN** система отображает рабочие зоны `GLAccount` и `GLAccountSet` вместе с существующими зонами master-data
- **AND** все операции выполняются в tenant scope без cross-tenant данных

### Requirement: Workspace MUST поддерживать role-specific, owner-scoped и chart-scoped bindings
Система ДОЛЖНА (SHALL) предоставлять в зоне `Bindings` явное управление scope-ключами binding:
- для `Party`: `(canonical_id, entity_type, database_id, ib_catalog_kind)`;
- для `Contract`: `(canonical_id, entity_type, database_id, owner_counterparty_id)`;
- для `Item/TaxProfile`: `(canonical_id, entity_type, database_id)`;
- для `GLAccount`: `(canonical_id, entity_type, database_id, chart_identity)`.

Система ДОЛЖНА (SHALL) отображать `chart_identity` и related compatibility markers как first-class operator-facing поля.

#### Scenario: UI показывает chart-scoped binding для GLAccount
- **GIVEN** оператор открывает bindings для canonical `GLAccount`
- **WHEN** в target database существует binding в конкретном chart of accounts
- **THEN** UI показывает `chart_identity` как часть binding scope
- **AND** оператор не воспринимает binding как generic database-only mapping

### Requirement: Document policy authoring MUST поддерживать guided master-data token picker
Система ДОЛЖНА (SHALL) в `/pools/catalog` предоставлять guided token picker для `field_mapping` и `table_parts_mapping` в `document_policy` builder.

Token picker ДОЛЖЕН (SHALL) генерировать токены совместимого формата:
- `master_data.party.<canonical_id>.<organization|counterparty>.ref`;
- `master_data.item.<canonical_id>.ref`;
- `master_data.contract.<canonical_id>.<owner_counterparty_canonical_id>.ref`;
- `master_data.tax_profile.<canonical_id>.ref`;
- `master_data.gl_account.<canonical_id>.ref`.

Token picker, sync affordances и entity catalogs ДОЛЖНЫ (SHALL) читать generated reusable-data registry contract, а не handwritten frontend enum list.

#### Scenario: Оператор выбирает GLAccount через token picker
- **GIVEN** оператор редактирует mapping документа в policy builder
- **WHEN** он выбирает account-typed поле и открывает token picker
- **THEN** система подставляет валидный token `master_data.gl_account.<canonical_id>.ref`
- **AND** доступность выбора определяется generated registry capability policy

## ADDED Requirements

### Requirement: Workspace MUST показывать capability-gated sync и revision states для reusable accounts
Система ДОЛЖНА (SHALL) явно показывать оператору shipped capability state reusable accounts:
- `GLAccount` как bootstrap-capable entity без generic mutating outbound/bidirectional sync actions;
- `GLAccountSet` как profile с draft/publish/revision lifecycle и non-actionable sync state.

#### Scenario: UI не показывает mutating sync controls для GLAccountSet
- **GIVEN** оператор открывает sync-oriented surface reusable-data workspace
- **WHEN** система строит список доступных действий из generated capability policy
- **THEN** `GLAccountSet` не появляется как mutating sync entity
- **AND** оператор видит его как profile/revision state, а не как direct target sync object

### Requirement: Shared reusable-data UI helpers MUST оставаться registry-driven и fail-closed
Система ДОЛЖНА (SHALL) строить operator-facing entity captions, bootstrap defaults, token catalogs и binding scope presentation из generated reusable-data registry contract, а не из raw `entity_type` строк или string-specific frontend conventions.

Система ДОЛЖНА (SHALL) явно сигнализировать compatibility gap, если registry публикует token-exposed entity type, для которого frontend adapter ещё не умеет materialize'ить picker catalog.

#### Scenario: Registry label и capability policy управляют account helper surfaces
- **GIVEN** registry публикует `entity_type=gl_account` с `label=GL Account` и token/bootstrap capabilities
- **WHEN** оператор открывает bindings, bootstrap import или token picker
- **THEN** UI показывает operator-facing caption `GL Account`
- **AND** page defaults и доступные действия вычисляются из registry contract без special-case string exclusions вроде `'binding'`

#### Scenario: Missing token adapter не скрывается silently
- **GIVEN** registry публикует token-exposed entity type, для которого frontend compatibility adapter ещё не реализован
- **WHEN** UI или tests строят token catalog snapshot
- **THEN** система возвращает явный compatibility gap вместо silent fallback
- **AND** unsupported entity type не считается автоматически доставленным в operator-facing token picker
