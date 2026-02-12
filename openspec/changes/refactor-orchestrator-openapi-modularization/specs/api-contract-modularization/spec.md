## ADDED Requirements
### Requirement: Orchestrator OpenAPI sources MUST поддерживать модульную структуру
Система ДОЛЖНА (SHALL) хранить редактируемые исходники public OpenAPI контракта orchestrator в модульной структуре `contracts/orchestrator/src/**` с разделением как минимум по `paths` и `components`.

Модульная структура ДОЛЖНА (SHALL) быть пригодной для локальных точечных правок без необходимости редактировать один большой файл контракта.

#### Scenario: Изменение endpoint выполняется в доменном модуле, а не в монолите
- **GIVEN** разработчик добавляет/меняет endpoint orchestrator API
- **WHEN** он вносит изменение в контракт
- **THEN** правка выполняется в соответствующем модульном файле под `contracts/orchestrator/src/**`
- **AND** ручное редактирование большого монолитного файла не требуется

### Requirement: Bundle artifact MUST оставаться единым входом для существующего toolchain
Система ДОЛЖНА (SHALL) собирать модульные исходники в единый файл `contracts/orchestrator/openapi.yaml`, который используется существующими скриптами валидации и генерации.

Bundle ДОЛЖЕН (SHALL) быть детерминированным: повторная сборка при неизменных исходниках не меняет содержимое артефакта.

#### Scenario: Validate и codegen работают через единый bundle
- **GIVEN** модульные исходники актуальны
- **WHEN** запускаются `./contracts/scripts/validate-specs.sh` и `./contracts/scripts/generate-all.sh`
- **THEN** оба скрипта используют `contracts/orchestrator/openapi.yaml` как входной контракт
- **AND** скрипты завершаются без ошибок, связанных с относительными `$ref`

### Requirement: Tooling MUST fail-fast при дрейфе source и bundle
Система ДОЛЖНА (SHALL) иметь проверку актуальности bundle относительно `contracts/orchestrator/src/**`.

Если bundle устарел, tooling ДОЛЖЕН (SHALL) завершаться с понятной диагностикой и инструкцией по пересборке.

#### Scenario: Устаревший bundle блокирует pipeline
- **GIVEN** разработчик изменил файл в `contracts/orchestrator/src/**`, но не пересобрал bundle
- **WHEN** запускается валидация контрактов
- **THEN** проверка завершается ошибкой "bundle out-of-date" (или эквивалентной)
- **AND** в сообщении есть команда/шаг для пересборки

### Requirement: Breaking changes detection MUST корректно работать при модульных исходниках
Система ДОЛЖНА (SHALL) выполнять проверку breaking changes по собранным bundle-файлам (base/current), чтобы относительные `$ref` не ломали сравнение.

#### Scenario: Проверка breaking changes не падает на относительных refs
- **GIVEN** orchestrator контракт хранится в модульных source-файлах
- **WHEN** запускается `./contracts/scripts/check-breaking-changes.sh`
- **THEN** скрипт сравнивает bundle base/current и корректно отрабатывает анализ изменений
- **AND** ошибка "cannot resolve relative ref" не возникает из-за временных путей

### Requirement: Migration на модульную структуру MUST сохранять API-семантику
Система ДОЛЖНА (SHALL) при переносе в модульную структуру сохранять API-семантику контракта: состав endpoint-ов, HTTP methods, `operationId`, и совместимые схемы `components`.

#### Scenario: После миграции API остаётся семантически эквивалентным
- **GIVEN** выполнена миграция orchestrator OpenAPI в `contracts/orchestrator/src/**`
- **WHEN** собран новый `contracts/orchestrator/openapi.yaml`
- **THEN** он сохраняет тот же набор endpoint-ов и `operationId`, что и до миграции
- **AND** не содержит непреднамеренных breaking changes
