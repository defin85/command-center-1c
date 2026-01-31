# Design: Preflight-валидация offline-подключения для `ibcmd_cli`

## Контекст
В `ibcmd_cli` режим `connection.offline` требует одновременно:
- DBMS “метаданных” подключения (тип СУБД, сервер, имя БД),
- DBMS credential mapping (`DbmsUserMapping`) для `db_user/db_password` (actor/service стратегия),
- (в зависимости от команды) IB credential mapping для `--user/--password`.

В системе часть параметров разрешается *per target database* на рантайме (worker), а часть задаётся на request-level в Configure.
Это нормально для 1С и соответствует тому, что один кластер 1С может обслуживать инфобазы на разных СУБД: поэтому DBMS metadata относится к конкретной базе, а не к кластеру.

## Проблема
Сейчас `execute_ibcmd_cli` валидирует некоторые запреты (например inline DBMS creds) и наличие DBMS mapping, но не проверяет наличие DBMS metadata.
В результате операция может быть поставлена в очередь и затем упасть на worker с ошибкой “missing DBMS credentials/metadata for offline connection: dbms, db_server, db_name”.

## Цель
Fail-fast: если offline-подключение заведомо неразрешимо, вернуть 400 до enqueue и дать пользователю понятный список “что отсутствует” по таргетам.

## Предлагаемое решение (MVP)
Добавить в `execute_ibcmd_cli` (для `scope=per_database`) preflight-валидацию offline DBMS metadata.

### Когда проверяем
Только если одновременно:
- `scope=per_database`
- НЕ задан `connection.remote`
- НЕ задан `connection.pid`
- `connection.offline.db_path` НЕ задан (это file infobase, DBMS metadata не требуется)

### Как резолвим значения (без worker)
Для каждого target database:
1) Берём request-level `connection.offline.dbms`, `connection.offline.db_server`, `connection.offline.db_name` если они заданы (не пустые).
2) Для отсутствующих значений используем per-target `Database.metadata.dbms/db_server/db_name`.
3) Если после этого остаются пустые обязательные поля — считаем таргет “не готов”.

### Error contract
HTTP 400:
```json
{
  "success": false,
  "error": {
    "code": "OFFLINE_DB_METADATA_NOT_CONFIGURED",
    "message": "Offline DBMS metadata is not configured for some databases",
    "details": {
      "missing": [
        {"database_id": "...", "database_name": "...", "missing_keys": ["dbms","db_server","db_name"]}
      ]
    }
  }
}
```

Ограничения:
- `details.missing` ограничиваем по размеру (например первые 25), остальное — счётчиком.
- Никаких секретов в payload.

### UI поведение
- UI показывает ошибку как “исправьте метаданные базы (DBMS/DB server/DB name) или задайте их в Configure”.
- Для случаев, где часть полей можно задать в Configure (например `dbms/db_server` общие), UI предлагает заполнить их в форме.
- Для per-target `db_name` UI показывает, что оно берётся из базы (или общий override) и без него запуск невозможен.

## Управление DBMS metadata (API + UI)
Цель — дать оператору контролируемый способ вручную заполнить `dbms/db_server/db_name`, если они не были импортированы автоматически (например из-за недостаточных прав RAS или нестандартного окружения).

### Где храним
Минимально и без миграций:
- продолжаем хранить в `Database.metadata` ключи `dbms`, `db_server`, `db_name`.

Это отражает доменную реальность 1С: одна инсталляция/кластер может обслуживать инфобазы на разных СУБД, поэтому метаданные относятся к конкретной базе, а не к кластеру.

### Endpoint (proposal)
`POST /api/v2/databases/update-dbms-metadata/`

Request:
```json
{
  "database_id": "uuid",
  "dbms": "PostgreSQL",
  "db_server": "db.example.local",
  "db_name": "stroygrupp",
  "reset": false
}
```

Правила:
- `reset=true` очищает `dbms/db_server/db_name`.
- При `reset=false` валидируем, что хотя бы одно поле задано, и заданные значения не пустые строки.
- RBAC: требуется `databases.manage_database` на базу.
- Tenant scope: база должна принадлежать текущему tenant контексту (как принято в проекте).

Response:
- Возвращаем обновлённую `database` (или минимум `database_id` + `metadata`), без секретов.

### UI (proposal)
- На странице `/databases` добавить действие “DBMS metadata” (доступно, если пользователь имеет MANAGE на базу).
- Модалка с 3 полями: DBMS / DB server / DB name + кнопки Save и Reset.
- После Save/Reset обновляем список баз (invalidate query).

## Альтернативы (не в MVP)
1) Делать “real preflight” через worker dry-run — избыточно и дороже, чем детерминированная проверка данных.
2) Хранить DBMS metadata отдельными колонками вместо `Database.metadata` — сильнее типизирует, но требует миграций и шире затрагивает код (не нужно для MVP).

## Риски
- Возможны ложные отрицания, если worker научится доставать metadata из других источников. В этом случае алгоритм резолва нужно расширять (это будет отдельный change).
- Нужно аккуратно сформулировать “обязательность” полей: `db_path` должен выключать DBMS metadata requirement.
- Ручное редактирование metadata может привести к неверным значениям и ошибкам выполнения. Митигируем:
  - ограничением прав (MANAGE),
  - минимальной валидацией формата (не пусто),
  - понятной ошибкой preflight/worker без утечек секретов.
