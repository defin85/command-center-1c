## ADDED Requirements
### Requirement: Pool catalog metadata client MUST использовать generated OpenAPI contract как единственный typed source-of-truth
Система ДОЛЖНА (SHALL) использовать generated OpenAPI client/models как единственный typed source-of-truth для shipped frontend path, который читает `/api/v2/pools/odata-metadata/catalog/` и `/api/v2/pools/odata-metadata/catalog/refresh/`.

Hand-written DTO или mirror-типы для этого surface НЕ ДОЛЖНЫ (SHALL NOT) оставаться runtime-контрактом default `/pools/catalog` metadata workspace.

Drift между runtime serializer, OpenAPI source, generated client и shipped frontend consumer ДОЛЖЕН (SHALL) блокировать релиз как quality gate.

Hand-written types МОГУТ (MAY) существовать только в isolated test/migration helpers, если они не участвуют в default shipped runtime path.

#### Scenario: Новые shared snapshot markers проходят через один source-of-truth
- **GIVEN** metadata catalog contract расширен новыми полями shared snapshot provenance
- **WHEN** обновляется OpenAPI source и выполняется codegen
- **THEN** shipped frontend consumer читает эти поля через generated model
- **AND** отдельный hand-written DTO не требуется для корректной типизации default path

#### Scenario: Drift между generated client и shipped consumer блокирует release
- **GIVEN** runtime/OpenAPI metadata catalog contract изменён
- **WHEN** generated client или frontend consumer не синхронизирован с новым контрактом
- **THEN** parity gate завершается ошибкой
- **AND** stale hand-written DTO не может silently оставаться источником истины для shipped path

## MODIFIED Requirements
### Requirement: Pool catalog workflow bindings MUST использовать isolated binding workspace и canonical CRUD
Система ДОЛЖНА (SHALL) управлять workflow bindings на `/pools/catalog` через dedicated binding workspace и dedicated binding endpoints, backed by the same canonical store, который использует runtime resolution.

Pool upsert contract НЕ ДОЛЖЕН (SHALL NOT) нести canonical binding payload и НЕ ДОЛЖЕН (SHALL NOT) переписывать binding state как side effect редактирования базовых полей пула.

Binding read path ДОЛЖЕН (SHALL) возвращать server-managed `revision`, а binding edit/delete flows в `/pools/catalog` ДОЛЖНЫ (SHALL) использовать этот `revision` для conflict-safe update/delete.

UI ДОЛЖЕН (SHALL) разделять:
- mutating операции над базовыми полями `pool`;
- mutating операции над `pool_workflow_binding`.

Для default multi-binding save UI ДОЛЖЕН (SHALL) использовать collection-level atomic save contract поверх canonical binding store и НЕ ДОЛЖЕН (SHALL NOT) полагаться на последовательность client-side `upsert/delete`, которая допускает partial apply.

При collection conflict UI ДОЛЖЕН (SHALL) сохранять введённые данные формы, показывать причину конфликта и предлагать reload canonical collection без потери локального edit state.

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

#### Scenario: Workspace-save не оставляет частично применённые bindings
- **GIVEN** оператор меняет набор bindings в isolated workspace
- **AND** один из элементов запроса конфликтует с более новой canonical collection
- **WHEN** UI отправляет multi-binding save
- **THEN** backend отклоняет весь save как единый conflict
- **AND** после reload оператор видит либо старую целую canonical collection, либо полностью новую, но не partial mix обоих состояний
