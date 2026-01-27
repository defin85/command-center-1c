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

### Requirement: UI для управления DBMS user mapping (admin-only)
Система ДОЛЖНА (SHALL) предоставлять в UI административный интерфейс для управления DBMS user mapping по выбранной базе:
- просмотр списка (actor mappings + service mapping);
- создание/редактирование/удаление записей;
- поиск/фильтрация (минимум: поиск по `db_username` и по связанному CC пользователю).

#### Scenario: Администратор управляет DBMS mappings для базы
- **GIVEN** пользователь является staff/admin
- **AND** выбрана база `database_id`
- **WHEN** пользователь открывает UI управления DBMS mappings
- **THEN** UI отображает список DBMS mappings для этой базы и позволяет выполнять CRUD операции

### Requirement: Пароль DBMS не отображается, управляется отдельными действиями
Система ДОЛЖНА (SHALL) обеспечивать, что UI никогда не отображает текущее значение DBMS пароля и не сохраняет его в shortcuts/конфигурациях операций. UI ДОЛЖЕН (SHALL) предоставлять отдельные действия:
- “Set password” (установить/заменить пароль);
- “Reset password” (сбросить пароль),
при этом отображать только признак “password configured”.

#### Scenario: Пароль доступен только через set/reset
- **GIVEN** существует DBMS mapping запись
- **WHEN** пользователь просматривает список DBMS mappings
- **THEN** UI показывает только `db_password_configured`
- **AND** UI позволяет выполнить “Set password” и “Reset password” без отображения текущего пароля

### Requirement: UI управления DBMS mappings недоступен не-staff пользователям
Система ДОЛЖНА (SHALL) не предоставлять UI управления DBMS mappings пользователям без staff/admin прав и корректно обрабатывать 403.

#### Scenario: Не-staff пользователь не видит функциональность
- **GIVEN** пользователь не является staff/admin
- **WHEN** пользователь открывает раздел управления DBMS mappings
- **THEN** UI скрывает функциональность или показывает сообщение об отсутствии прав
- **AND** система не раскрывает список mappings

