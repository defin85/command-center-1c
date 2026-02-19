## ADDED Requirements
### Requirement: CI MUST выполнять обязательные OpenAPI contract gates
Система ДОЛЖНА (SHALL) запускать обязательный CI job для проверки API-контрактов при интеграции изменений в основную ветку.

CI job ДОЛЖЕН (SHALL) последовательно выполнять:
- `./contracts/scripts/build-orchestrator-openapi.sh check`
- `./contracts/scripts/validate-specs.sh`
- `./contracts/scripts/check-breaking-changes.sh`

#### Scenario: Изменение контракта проверяется всеми gate-скриптами
- **GIVEN** разработчик изменил OpenAPI контракт или связанные contract scripts
- **WHEN** запускается CI pipeline для merge/promotion
- **THEN** выполняются все обязательные contract gates
- **AND** результат pipeline отражает итог выполнения каждого gate

### Requirement: CI contract gates MUST быть блокирующими
Система ДОЛЖНА (SHALL) завершать pipeline ошибкой, если любой обязательный contract gate завершился неуспешно.

#### Scenario: Любой failing gate блокирует интеграцию
- **GIVEN** один из обязательных contract gates завершился ошибкой
- **WHEN** CI оценивает статус job/pipeline
- **THEN** pipeline помечается как failed
- **AND** merge/promotion блокируется до исправления ошибки

### Requirement: CI MUST использовать strict режим проверок контрактов
Система ДОЛЖНА (SHALL) выполнять contract gates в CI-контексте (`CI=true`) и не допускать ослабляющих fallback-режимов для обязательных проверок.

#### Scenario: Отсутствие обязательного инструмента в CI приводит к failed pipeline
- **GIVEN** в CI отсутствует обязательный инструмент проверки (например, `oasdiff` для breaking-check или полноценный OpenAPI validator)
- **WHEN** запускается соответствующий contract gate
- **THEN** gate завершается ошибкой
- **AND** pipeline помечается как failed
