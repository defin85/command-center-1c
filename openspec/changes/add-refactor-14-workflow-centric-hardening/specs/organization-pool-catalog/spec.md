## MODIFIED Requirements
### Requirement: Metadata catalog retrieval MUST использовать persisted snapshot в БД и Redis только как ускоритель
Система ДОЛЖНА (SHALL) хранить нормализованный metadata catalog как canonical persisted snapshot, пригодный для reuse между несколькими ИБ в рамках одной tenant-scoped configuration signature, а не как database-local current snapshot по `database_id` alone.

Canonical metadata snapshot scope ДОЛЖЕН (SHALL) включать:
- `config_name`;
- `config_version`;
- `extensions_fingerprint` или эквивалентный marker extensions/applicability state;
- `metadata_hash` или эквивалентный fingerprint опубликованной OData metadata surface.

Canonical snapshot identity НЕ ДОЛЖНА (SHALL NOT) включать `database_id` после cutover. Конкретная ИБ ДОЛЖНА (SHALL) использоваться только как live refresh/probe source и provenance anchor для shared snapshot.

Read/refresh path МОЖЕТ (MAY) стартовать от выбранной ИБ, но:
- конкретная ИБ ДОЛЖНА (SHALL) использоваться только как auth/probe source и provenance anchor;
- identical normalized metadata payload ДОЛЖЕН (SHALL) переиспользовать один canonical snapshot across compatible infobases;
- система НЕ ДОЛЖНА (SHALL NOT) считать одинаковый `config_version` достаточным условием reuse, если published OData metadata surface различается.

Ответ metadata catalog API ДОЛЖЕН (SHALL) возвращать resolved snapshot scope/version markers, provenance о последней ИБ, подтвердившей snapshot, и указывать, что snapshot shared/reused на configuration scope, если это применимо.

#### Scenario: Две ИБ с одинаковой конфигурацией переиспользуют один canonical metadata snapshot
- **GIVEN** в tenant есть две ИБ с одинаковыми `config_name`, `config_version`, `extensions_fingerprint`
- **AND** normalized OData metadata payload у них совпадает
- **WHEN** оператор запрашивает metadata catalog для второй ИБ после refresh первой
- **THEN** backend возвращает тот же canonical snapshot
- **AND** response показывает configuration-scoped version markers вместо database-local uniqueness
- **AND** provenance указывает, какая ИБ последней подтвердила shared snapshot

#### Scenario: Одинаковая версия конфигурации, но разная OData surface не переиспользует snapshot молча
- **GIVEN** две ИБ показывают одинаковый `config_version`
- **AND** состав опубликованных через OData metadata objects различается
- **WHEN** backend refresh'ит metadata catalog для второй ИБ
- **THEN** система создаёт или резолвит другой canonical snapshot
- **AND** reuse первого snapshot не выполняется silently

### Requirement: Topology editor UI MUST поддерживать интерактивное создание Document policy и Edge metadata
Система ДОЛЖНА (SHALL) предоставлять в `/pools/catalog` topology editor для structural `node.metadata` / `edge.metadata` и explicit compatibility path для legacy `edge.metadata.document_policy`.

После поставки replacement decision-resource authoring UI topology editor НЕ ДОЛЖЕН (SHALL NOT) оставаться primary surface для net-new `document_policy` authoring.

Для legacy edge `document_policy` UI ДОЛЖЕН (SHALL):
- показывать existing policy read-only по умолчанию;
- требовать явное compatibility/migration действие для открытия legacy editor;
- предоставлять explicit compatibility shortcut/handoff к canonical import surface на `/decisions` и к тому же migration contract для decision resource + selected binding refs;
- показывать migration provenance и целевые refs после успешного импорта.

#### Scenario: Оператор запускает compatibility shortcut из `/pools/catalog` для legacy edge policy
- **GIVEN** topology edge содержит legacy `document_policy`
- **AND** для пула существует workflow-centric binding
- **WHEN** оператор запускает explicit compatibility action из `/pools/catalog`
- **THEN** UI использует тот же deterministic migration contract, что и canonical import surface на `/decisions`
- **AND** topology editor показывает migration outcome и направляет оператора на decision-resource lifecycle вместо продолжения direct edge authoring как primary path

#### Scenario: Новый topology edge не навязывает direct document_policy authoring
- **GIVEN** оператор добавляет новый edge в topology editor
- **WHEN** UI рендерит controls для edge metadata
- **THEN** structural metadata остаётся доступной
- **AND** primary guidance направляет автора на route `/decisions` для net-new `document_policy`

### Requirement: UI MUST сохранять raw JSON fallback и round-trip совместимость metadata
Система ДОЛЖНА (SHALL) сохранять round-trip совместимость legacy `edge.metadata` и migration payload при explicit compatibility/migration path.

Система НЕ ДОЛЖНА (SHALL NOT) терять:
- пользовательские/неизвестные keys `edge.metadata`;
- legacy `document_policy`, пока migration не подтверждена;
- provenance связи между legacy edge и resulting decision resource revision.

Raw JSON fallback МОЖЕТ (MAY) использоваться в explicit compatibility или decision-resource editor, но НЕ ДОЛЖЕН (SHALL NOT) оставаться default topology authoring mode для новых workflow-centric схем.

#### Scenario: Migration path сохраняет unknown metadata keys и provenance
- **GIVEN** legacy edge содержит `document_policy` и дополнительные unknown metadata keys
- **WHEN** оператор выполняет migration/import
- **THEN** unknown keys `edge.metadata` сохраняются без потери
- **AND** UI/backend фиксируют provenance `edge -> decision revision -> binding ref`

## ADDED Requirements
### Requirement: Pool catalog workflow bindings MUST использовать isolated binding workspace и canonical CRUD
Система ДОЛЖНА (SHALL) управлять workflow bindings на `/pools/catalog` через dedicated binding workspace и dedicated binding endpoints, backed by the same canonical store, который использует runtime resolution.

Pool upsert contract НЕ ДОЛЖЕН (SHALL NOT) нести canonical binding payload и НЕ ДОЛЖЕН (SHALL NOT) переписывать binding state как side effect редактирования базовых полей пула.

Binding read path ДОЛЖЕН (SHALL) возвращать server-managed `revision`, а binding edit/delete flows в `/pools/catalog` ДОЛЖНЫ (SHALL) использовать этот `revision` для conflict-safe update/delete.

UI ДОЛЖЕН (SHALL) разделять:
- mutating операции над базовыми полями `pool`;
- mutating операции над `pool_workflow_binding`.

#### Scenario: Сохранение базовых полей пула не переписывает workflow bindings
- **GIVEN** оператор редактирует `code` или `name` пула в `/pools/catalog`
- **AND** у пула уже есть active workflow bindings
- **WHEN** оператор сохраняет только базовые поля пула
- **THEN** UI использует pool upsert path без canonical binding payload
- **AND** существующие workflow bindings не теряются и не переписываются

#### Scenario: Binding editor использует тот же canonical CRUD, что и runtime
- **GIVEN** оператор добавляет или удаляет workflow binding в `/pools/catalog`
- **WHEN** изменение сохраняется
- **THEN** UI обращается к dedicated binding CRUD endpoint'ам
- **AND** следующий create-run/read-model видит это же изменение без дополнительного metadata sync шага

#### Scenario: Stale binding revision в catalog editor возвращает conflict без потери формы
- **GIVEN** оператор редактирует workflow binding в `/pools/catalog`
- **AND** другой оператор уже сохранил новую `revision`
- **WHEN** первый оператор пытается отправить устаревшее состояние
- **THEN** backend возвращает machine-readable conflict по `revision`
- **AND** UI сохраняет введённые данные для повторной попытки
