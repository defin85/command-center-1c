## Контекст
`ibcmd` поддерживает offline‑подключение к СУБД через набор общих флагов (4.10.2). Эти флаги сейчас попадают в `driver_schema` и рендерятся в UI как единый список полей.

Проблемы:
- UX: слишком много опций в одном списке, тяжело найти нужное и легко ошибиться.
- Security: DBMS креды попадают в UI state (и потенциально могут попасть в ярлыки/логи).
- Correctness: для `per_database` команды операция может иметь несколько таргетов, но offline‑connection параметры (включая `db_name`) и креды могут отличаться по таргетам.
- Shortcuts: текущая модель ярлыков сохраняет только `command_id`, не воспроизводит конфигурацию.

## Цели / Non-goals
### Goals
- Сделать `Driver options` управляемыми: показывать “важное”, остальное прятать в Advanced/Collapsed.
- Не вводить DBMS креды руками в `DriverCommandBuilder`; резолвить их через маппинг/секреты.
- Сделать ярлыки воспроизводимыми и безопасными: сохранять конфиг без секретов, валидировать/мигрировать при изменениях схемы.
- Поддержать per‑target резолв DBMS connection/creds для `ibcmd` per‑database операций (N таргетов).

### Non-goals (на этом change)
- Не делаем универсальный “секретный менеджер” для всех драйверов; область — DBMS креды для `ibcmd`.
- Не делаем сложную дедупликацию DBMS маппингов между базами/кластерами (можно добавить позже).

## Основные решения
### 1) DBMS creds как credential mapping (аналог `InfobaseUserMapping`)
- Добавить модель `DbmsUserMapping` (или аналогичное имя) в `apps/databases`:
  - `database` (FK), `user` (FK, nullable), `db_username`, `db_password` (encrypted),
  - `auth_type`, `is_service`, `notes`, audit поля (created_by/updated_by).
- Добавить policies:
  - actor mapping: по `request.user` + `target database`.
  - service mapping: по `target database` (is_service=true) и только для allowlist safe операций (как и для IB service).

### 2) Резолв per-target для `connection.offline.*`
Для `scope=per_database` резолвить `connection.offline.dbms/db_server/db_name/db_path` и DBMS creds отдельно для каждого таргета.

Рекомендуемая граница:
- API валидирует input, строит канонический план и фиксирует provenance (что будет резолвиться на worker).
- Worker, имея `task.database_id`, загружает metadata/маппинг и строит финальный `argv[]` для этого таргета.

Для `scope=global`:
- Использовать `auth_database_id` как “anchor database” и резолвить connection/creds из неё (аналогично текущей логике auth context).

Важно: “Configure” параметры должны применяться к выбранному списку баз (N >= 1) как общий шаблон конфигурации, который затем дополняется/переопределяется per target значениями.
Например:
- пользователь в UI выбирает N баз (Target step);
- в Configure step задаёт команду и общие driver options (например `--dbms`, `--db-server`, `timeout_seconds`, `ib_auth.strategy`);
- при исполнении для каждой базы worker обязан подставить per target значения (минимум `--db-name`, а при необходимости и другие offline‑параметры), без необходимости вручную заполнять N разных конфигов.

### 3) UI оптимизация driver options
UI должен:
- разделять `Connection` на подгруппы (“DB connection”, “Storage paths”, “Advanced”), по умолчанию показывать “DB connection” + только заполненные поля;
- скрыть DBMS креды поля полностью и отображать текст “DB credentials are resolved by mapping”;
- позволять быстро найти опцию (поиск остаётся), и не раздувать экран за счёт collapsible панелей.

### 4) Shortcuts v2: воспроизводимость + миграция
Изменить shortcut модель/контракт:
- хранить `payload` (json) с конфигурацией команды (без секретов), минимум:
  - `mode`, `params`, `additional_args` (или `args_text`), `connection` (без `db_user/db_pwd`), `timeout_seconds`, `stdin` (опционально), `ib_auth.strategy`, `auth_database_id` (если уместно).
- хранить метаданные “с какой схемой сохраняли”:
  - `catalog_base_version`, `catalog_overrides_version`, `command_id`, и/или hash effective schema.
- при загрузке ярлыка делать нормализацию:
  - неизвестные поля/пути drop с предупреждением;
  - значения, противоречащие enum/value_type, помечать как invalid и требовать ручного исправления.

## Альтернативы
1) Оставить DBMS креды в UI, но сделать “скрытое поле” и не сохранять в shortcut.
   - Минус: всё равно остаётся риск утечек через UI state/скриншоты/ошибки пользователя.
2) Резолв per-target делать на API (строить N разных `argv` заранее).
   - Минус: тяжелее/дороже; хуже разделение ответственности и сложнее provenance (но возможно для preview staff-only).

## Риски
- Нужно аккуратно мигрировать существующие флоу/шаблоны, где DBMS креды задавались вручную.
- Нужны понятные ошибки и инструкции пользователю, когда маппинг отсутствует для выбранных таргетов.
- Shortcuts должны быть безопасны: запрет на сохранение `stdin`/опасных параметров может потребовать отдельной политики.
