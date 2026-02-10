## MODIFIED Requirements
### Requirement: Обзор расширений по всем базам
Система ДОЛЖНА (SHALL) предоставлять экран `/extensions` как templates-first интерфейс обзорного управления и ручного запуска атомарных операций `extensions.*`.

#### Scenario: Ручная операция запускается по явному manual contract и выбранному template
- **GIVEN** пользователь открыл drawer расширения на `/extensions`
- **WHEN** выбирает ручную операцию (например `extensions.set_flags`), выбирает template и подтверждает запуск
- **THEN** UI вызывает единый template-based `extensions plan/apply` pipeline
- **AND** backend резолвит executor через `template_id`

## ADDED Requirements
### Requirement: `/extensions` MUST не зависеть от action catalog runtime controls
Система НЕ ДОЛЖНА (SHALL NOT) использовать action-catalog controls на `/extensions`.

#### Scenario: UI не показывает action-catalog элементы управления
- **GIVEN** пользователь находится на `/extensions`
- **WHEN** открывает панель ручного запуска
- **THEN** отсутствуют selector/alerts/navigation, связанные с Action Catalog
- **AND** доступны только templates-based controls

## REMOVED Requirements
### Requirement: Workflow-first bulk управление флагами и расширениями
**Reason**: в этом change `/extensions` фиксируется как templates-only manual execution flow для атомарных операций.
**Migration**: workflow execution остаётся отдельным контуром оркестрации, не как runtime source для manual controls.

### Requirement: Точечное управление остаётся fallback-режимом
**Reason**: модель fallback удаляется; остаётся единый templates-based execution path.
**Migration**: использовать тот же template-based plan/apply без fallback маркировки.
