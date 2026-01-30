# tenancy Specification

## Purpose
TBD - created by archiving change add-tenancy-extensions-plan-apply. Update Purpose after archive.
## Requirements
### Requirement: Tenant как изоляционный домен
Система ДОЛЖНА (SHALL) поддерживать `Tenant` как изоляционный домен данных и конфигураций.

#### Scenario: База принадлежит ровно одному tenant
- **GIVEN** база создана в системе
- **WHEN** база сохранена
- **THEN** база имеет `tenant_id` и не может принадлежать двум tenants одновременно

### Requirement: UI-переключатель tenant и tenant context в API
Система ДОЛЖНА (SHALL) позволять пользователю выбрать активный tenant в UI и использовать его для всех API запросов.

#### Scenario: Запросы tenant-scoped
- **GIVEN** пользователь выбрал tenant A
- **WHEN** UI выполняет запросы к API
- **THEN** запросы исполняются в контексте tenant A и не раскрывают данные tenant B

### Requirement: Membership enforcement
Система ДОЛЖНА (SHALL) запрещать доступ к tenant без membership.

#### Scenario: Нет доступа к чужому tenant
- **GIVEN** пользователь не является member tenant B
- **WHEN** он пытается выполнить запрос в контексте tenant B
- **THEN** API возвращает 403 и не раскрывает данные tenant B

### Requirement: Миграция в default tenant
Система ДОЛЖНА (SHALL) при включении tenancy создать `default` tenant и мигрировать существующие данные в него.

#### Scenario: Существующие кластеры/базы доступны после миграции
- **GIVEN** в системе уже есть кластеры/базы до tenancy
- **WHEN** выполнена миграция
- **THEN** кластеры/базы принадлежат `default` tenant и доступны согласно RBAC

