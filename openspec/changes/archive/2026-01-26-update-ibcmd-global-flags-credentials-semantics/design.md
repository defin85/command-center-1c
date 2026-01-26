# Design: update-ibcmd-global-flags-credentials-semantics

## Контекст
`ibcmd` — schema-driven драйвер. В документации (раздел 4.10.2 “Общие параметры”) определён широкий набор driver-level флагов, включая параметры offline‑подключения к СУБД и параметры выполнения/хранилищ данных автономного сервера.

Проблема: в текущей реализации драйверная схема отражает лишь малую часть этих флагов и не описывает семантику credential‑параметров, из-за чего невозможно типово и безопасно:
- показывать все driver options в UI;
- маскировать/валидировать секреты;
- однозначно инжектить одновременно креды СУБД и ИБ.

## Цели
1) Полностью отобразить флаги 4.10.2 в `ibcmd.driver_schema` (как persistent/global flags).
2) Добавить машиночитаемую семантику credential‑флагов, чтобы:
   - UI мог корректно рендерить (включая password widgets),
   - builder мог маскировать,
   - worker мог инжектить значения.
3) Ввести поддерживаемую и ограниченную политику service‑аутентификации в ИБ для allowlist safe‑команд.
4) Исключить необходимость stdin/pty/expect: работаем только через argv‑флаги для DB/IB creds.

## Нецели
- Поддержка `--request-db-pwd (-W)` в guided режиме (stdin).
- Автосоздание сервисного пользователя в ИБ.

## Термины
- DBMS creds: `db_user`, `db_password` (offline).
- Infobase creds: `ib_user`, `ib_password`.
- Strategy:
  - actor: per-user mapping (по `created_by`);
  - service: сервисный mapping для базы (`is_service=true`, `user=NULL`);
  - none: не инжектим IB creds.

## Предлагаемая модель данных

### 1) Расширение driver_schema для `ibcmd`
`driver_schema.connection` расширяется до полного набора флагов 4.10.2.

Для каждого flag-поля добавляются (опционально):
- `aliases: string[]` — все поддерживаемые алиасы (например `--database-password`, `--db-pwd`).
- `sensitive: boolean` — признак секрета (для маскирования).
- `semantics: { credential_kind?: \"db_user\"|\"db_password\"|\"ib_user\"|\"ib_password\" }` — для идентификации credential-полей.

Примечание: `semantics.credential_kind` используется только для небольшого поднабора полей, которые относятся к кредам.

### 2) Новое driver-level поле выбора IB auth стратегии
Добавляется `driver_schema.ib_auth.strategy`:
- kind: enum
- values: `actor|service|none`
- default: `actor` (для per_database команд, требующих IB auth)
- UI: отдельная секция `Auth`/`Infobase auth`.

API валидирует `strategy=service` по правилам доступа (см. ниже).

### 3) Политика доступа (RBAC/allowlist)
`ib_auth.strategy=service` разрешён только если:
- `command.risk_level == safe`;
- `command_id` находится в allowlist (первый этап: `infobase.extension.list`, `infobase.extension.sync` или эквиваленты);
- пользователь имеет отдельное разрешение (permission) или является staff (конкретное имя permission определяется в реализации).

Иначе — fail closed (ошибка валидации на API).

## Сборка argv и кредов (end-to-end)

### API (orchestrator)
- Ставит в очередь канонический `argv[]` (и `argv_masked[]`) с driver-level флагами + command params + additional_args.
- Секреты маскируются в `argv_masked[]`.
- `bindings[]` отмечают источники (request / connection / credentials.*), с `sensitive=true` без raw значений.

### Worker
Worker получает task + `argv[]` и выполняет runtime-resolve:
- Инжект DBMS creds из `connection.offline.db_user/db_pwd` (argv-only).
- Инжект IB creds в `--user/--password` в зависимости от `ib_auth.strategy`:
  - actor: из per-user mapping;
  - service: из mapping `is_service=true`.
- Для `service` worker дополнительно проверяет, что команда разрешена (defense in depth).

## Совместимость и миграция
- Новые поля в запросе/схеме опциональны, старые клиенты продолжают работать.
- В раннем этапе allowlist ограничен только safe‑командами extensions list/sync.

