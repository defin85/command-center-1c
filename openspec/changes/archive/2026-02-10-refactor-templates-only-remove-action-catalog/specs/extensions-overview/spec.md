## MODIFIED Requirements
### Requirement: Обзор расширений по всем базам
Система ДОЛЖНА (SHALL) использовать `/extensions` как templates-only manual operations экран для домена extensions.

#### Scenario: Ручная операция запускается через manual-operation контракт
- **GIVEN** пользователь открыл drawer расширения на `/extensions`
- **WHEN** выбирает `manual_operation`, template и подтверждает запуск
- **THEN** UI вызывает template-based `extensions plan/apply`
- **AND** backend резолвит executor через template contract

## ADDED Requirements
### Requirement: `/extensions` MUST поддерживать preferred template bindings
Система ДОЛЖНА (SHALL) использовать tenant preferred template binding per manual operation.

#### Scenario: UI подставляет preferred template по умолчанию
- **GIVEN** для `manual_operation="extensions.sync"` настроен preferred template
- **WHEN** пользователь открывает запуск операции
- **THEN** UI подставляет этот template по умолчанию
- **AND** пользователь может переопределить template для конкретного запуска

### Requirement: Preferred template bindings MUST иметь явный read/write API контракт
Система ДОЛЖНА (SHALL) предоставлять tenant-scoped API для управления preferred template bindings:
- `GET /api/v2/extensions/manual-operation-bindings/`,
- `PUT /api/v2/extensions/manual-operation-bindings/{manual_operation}/`,
- `DELETE /api/v2/extensions/manual-operation-bindings/{manual_operation}/`.

#### Scenario: PUT binding с несовместимым template отклоняется
- **WHEN** клиент вызывает `PUT /api/v2/extensions/manual-operation-bindings/{manual_operation}/` с `template_id`, несовместимым с `manual_operation`
- **THEN** backend возвращает `HTTP 400` (`CONFIGURATION_ERROR`)
- **AND** persisted binding не изменяется

#### Scenario: DELETE binding удаляет fallback
- **GIVEN** для `manual_operation` существовал preferred binding
- **WHEN** клиент вызывает `DELETE /api/v2/extensions/manual-operation-bindings/{manual_operation}/`
- **THEN** binding удаляется
- **AND** следующий запуск без `template_id` override завершается `MISSING_TEMPLATE_BINDING`

### Requirement: `/databases` MUST запускать extensions manual operations напрямую
Система ДОЛЖНА (SHALL) позволять запуск manual operations домена extensions прямо из `/databases`, используя тот же backend контракт, что и `/extensions`.

#### Scenario: Запуск из `/databases` использует единый pipeline
- **WHEN** пользователь запускает extensions manual operation из `/databases`
- **THEN** UI вызывает тот же `extensions plan/apply` flow
- **AND** action-catalog path не используется

### Requirement: Action-catalog runtime controls MUST отсутствовать
Система НЕ ДОЛЖНА (SHALL NOT) отображать action-catalog controls на `/extensions` и `/databases`.

#### Scenario: UI не показывает action-catalog controls
- **WHEN** пользователь открывает controls запуска
- **THEN** отсутствуют selector/alerts/navigation, связанные с Action Catalog
- **AND** доступен только templates/manual operations UX

## REMOVED Requirements
### Requirement: Workflow-first bulk управление флагами и расширениями
**Reason**: manual operations слой фиксируется как primary execution контракт для этого capability.
**Migration**: workflow остаётся отдельным orchestration контуром вне manual operations runtime-контракта.

### Requirement: Точечное управление остаётся fallback-режимом
**Reason**: fallback модель удаляется.
**Migration**: используется единый templates/manual operations path.
