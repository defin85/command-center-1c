# database-dbms-metadata Specification

## Purpose
TBD - created by archiving change add-ibcmd-offline-preflight-validation. Update Purpose after archive.
## Requirements
### Requirement: Управление DBMS metadata базы (dbms/db_server/db_name)
Система ДОЛЖНА (SHALL) позволять вручную устанавливать и сбрасывать DBMS metadata для конкретной базы данных (инфобазы) в CommandCenter:
- `dbms`
- `db_server`
- `db_name`

Эти значения предназначены для offline-подключения `ibcmd` и относятся к конкретной базе (а не к кластеру), так как один кластер 1С может обслуживать инфобазы на разных СУБД.

#### Scenario: Пользователь с правом MANAGE задаёт DBMS metadata
- **GIVEN** пользователь имеет право `databases.manage_database` на базу
- **WHEN** пользователь отправляет запрос на обновление DBMS metadata базы
- **THEN** система сохраняет `dbms/db_server/db_name` в данных базы
- **AND** последующий запуск `ibcmd_cli` в `connection.offline` может использовать эти значения как per-target fallback

#### Scenario: Пользователь без MANAGE не может редактировать DBMS metadata
- **GIVEN** пользователь НЕ имеет право `databases.manage_database` на базу
- **WHEN** пользователь пытается обновить DBMS metadata базы
- **THEN** система возвращает 403 и не изменяет данные

#### Scenario: Сброс DBMS metadata очищает значения
- **GIVEN** у базы заданы `dbms/db_server/db_name`
- **WHEN** пользователь выполняет действие “reset”
- **THEN** система очищает `dbms/db_server/db_name`
- **AND** запуск offline без request-level override и без заполненной metadata возвращает отказ preflight-валидации

