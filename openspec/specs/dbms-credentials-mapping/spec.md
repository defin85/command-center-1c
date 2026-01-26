# dbms-credentials-mapping Specification

## Purpose
TBD - created by archiving change update-ibcmd-driver-options-ui-shortcuts-dbms-credentials. Update Purpose after archive.
## Requirements
### Requirement: DBMS credential mapping (CC user ↔ DBMS user) по database
Система ДОЛЖНА (SHALL) поддерживать хранение и управление маппингом CC пользователей на DBMS креды для конкретной базы:
- `db_username`
- `db_password` (encrypted at rest)
- тип аутентификации и признак service‑аккаунта

#### Scenario: Администратор заводит DBMS маппинг
- **GIVEN** администратор имеет права управления маппингами
- **WHEN** он создаёт/обновляет маппинг для `database_id` и CC user (или service mapping)
- **THEN** система сохраняет `db_username` и `db_password` в защищённом виде

### Requirement: Разрешение на использование service DBMS mapping ограничено
Система ДОЛЖНА (SHALL) ограничивать использование service‑маппинга DBMS:
- только для allowlist safe операций (минимум: операции чтения extensions/sync)
- и только для пользователей с явным разрешением (RBAC/permission или staff).

#### Scenario: service DBMS mapping запрещён вне allowlist
- **WHEN** пользователь пытается выполнить команду вне allowlist с DBMS service mapping
- **THEN** система возвращает ошибку валидации и не создаёт операцию

### Requirement: Поведение при отсутствии DBMS mapping
Система ДОЛЖНА (SHALL) fail closed, если для таргета отсутствует требуемый DBMS маппинг, и выдавать понятную ошибку, не раскрывающую секреты.

#### Scenario: Нет маппинга для части таргетов
- **GIVEN** выбраны N таргетов
- **AND** для части таргетов отсутствует DBMS mapping
- **WHEN** пользователь запускает операцию
- **THEN** система отказывает с ошибкой, указывая какие таргеты не сконфигурированы (без раскрытия паролей)

