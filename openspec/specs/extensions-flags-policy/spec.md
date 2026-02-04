# extensions-flags-policy Specification

## Purpose
TBD - created by archiving change update-extensions-flags-policy-and-actions. Update Purpose after archive.
## Requirements
### Requirement: Tenant-scoped policy для флагов расширений
Система ДОЛЖНА (SHALL) хранить tenant-scoped policy для трёх флагов расширения (`active`, `safe_mode`, `unsafe_action_protection`) по ключу `extension_name`.

#### Scenario: Policy доступна в overview
- **GIVEN** tenant A настроил policy для расширения `X`
- **WHEN** пользователь в контексте tenant A запрашивает `GET /api/v2/extensions/overview/`
- **THEN** строки по `X` содержат соответствующие policy значения

### Requirement: Mutating policy операции требуют явного tenant context для staff
Система ДОЛЖНА (SHALL) fail-closed запрещать staff выполнять mutating операции policy без явного tenant context.

#### Scenario: Staff без X-CC1C-Tenant-ID не может менять policy
- **GIVEN** пользователь staff
- **WHEN** он вызывает `PATCH/PUT` policy endpoint без `X-CC1C-Tenant-ID`
- **THEN** API возвращает ошибку (400/403) и НЕ изменяет данные

