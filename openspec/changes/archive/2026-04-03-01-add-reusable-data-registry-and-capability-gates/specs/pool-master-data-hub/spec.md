## ADDED Requirements

### Requirement: Reusable-data type model MUST быть registry-driven и executable
Система ДОЛЖНА (SHALL) описывать reusable-data entity types через backend-owned executable registry/type-handler contract, а не через набор несвязанных enum/switch списков.

Registry ДОЛЖЕН (SHALL) определять как минимум:
- canonical entity key;
- binding scope contract;
- token exposure;
- bootstrap eligibility;
- sync/outbox eligibility;
- runtime consumers.

Backend-owned registry ДОЛЖЕН (SHALL) materialize-иться в generated shared contract/schema для `contracts/**` и frontend.
Система НЕ ДОЛЖНА (SHALL NOT) поддерживать handwritten duplicated registry definition в UI как parallel source-of-truth.

#### Scenario: Frontend и backend читают один registry contract
- **GIVEN** backend registry уже определяет reusable-data types и их capabilities
- **WHEN** contracts pipeline публикует generated registry artifact
- **THEN** frontend token catalogs и backend runtime gating используют одно и то же capability решение
- **AND** новая capability policy не требует ручной синхронизации нескольких enum lists

#### Scenario: Новый reusable entity type подключается через handler, а не через scattered enum edits
- **GIVEN** команда добавляет новый reusable entity type после foundation change
- **WHEN** она регистрирует type handler в executable registry
- **THEN** система получает один source-of-truth для routing и validation
- **AND** подключение не требует создания второго ad hoc каталога reusable data

### Requirement: Reusable-data capabilities MUST default fail-closed
Система ДОЛЖНА (SHALL) трактовать отсутствие явно объявленной capability как запрет на соответствующий runtime path.

Система НЕ ДОЛЖНА (SHALL NOT) считать наличие `entity_type` в enum, API namespace или binding storage достаточным основанием для:
- sync enqueue;
- outbox fan-out;
- bootstrap import;
- token exposure;
- mutating runtime actions.

#### Scenario: Новый entity type не становится исполнимым только из-за появления в enum
- **GIVEN** entity type добавлен в backend API surface, но registry capability для sync/outbox не объявлена
- **WHEN** runtime оценивает eligibility этого типа
- **THEN** sync enqueue и outbox fan-out остаются заблокированными
- **AND** система завершает проверку fail-closed вместо implicit enablement
