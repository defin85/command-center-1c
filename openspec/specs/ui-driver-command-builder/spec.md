# Спецификация: ui-driver-command-builder

## Purpose
Определяет требования к унифицированному UI компонента `DriverCommandBuilder` для schema-driven драйверов (`cli`, `ibcmd`) во всех местах использования (операции, templates, редакторы и т.п.).
## Requirements
### Requirement: Единый layout DriverCommandBuilder для `cli` и `ibcmd`
Система ДОЛЖНА (SHALL) предоставлять единый и предсказуемый layout формы `DriverCommandBuilder` во всех местах использования (операции, templates, редакторы), вне зависимости от драйвера (`cli`/`ibcmd`).

#### Scenario: Пользователь видит одинаковую структуру секций
- **GIVEN** пользователь открыл `DriverCommandBuilder` для `driver=cli`
- **WHEN** пользователь переключается на `driver=ibcmd` (в другом action/операции)
- **THEN** порядок и названия ключевых секций одинаковы: `Command` → `Mode` → `Parameters/Arguments` → `Driver options` → `Preview` → `Safety/Risk` (если применимо)

### Requirement: Driver options рендерятся из driver schema
Система ДОЛЖНА (SHALL) рендерить driver-level поля (например `connection.*`, `timeout_seconds`, `stdin`, `cli_options.*`) на основе `driver_schema`, а не на основе hardcoded UI‑форм.

#### Scenario: IBCMD execution context отображается как driver options
- **GIVEN** выбран `driver=ibcmd` и команда
- **WHEN** UI отображает форму
- **THEN** поля `connection.*`, offline‑поля, timeout, stdin и auth context отображаются в секции `Driver options` и управляются правилами `driver_schema`

### Requirement: Auth context для маппинга пользователя (RBAC)
Система ДОЛЖНА (SHALL) трактовать `auth_database_id` как auth context для RBAC и маппинга пользователя CommandCenter ↔ infobase user, а не как таргет выполнения.

#### Scenario: Auth context обязателен для global-scope `ibcmd`
- **GIVEN** выбран `driver=ibcmd` и команда с `scope=global`
- **WHEN** пользователь пытается перейти дальше без выбранного `auth_database_id`
- **THEN** UI/валидация блокирует продолжение и показывает понятную причину

#### Scenario: Auth context выбирается из выбранных таргетов
- **GIVEN** пользователь выбрал список target databases (N >= 1)
- **WHEN** UI предлагает выбор `auth_database_id`
- **THEN** options строятся из выбранных таргетов, отфильтрованных по RBAC (OPERATE)

### Requirement: Dangerous confirmation имеет единые правила
Система ДОЛЖНА (SHALL) использовать единый confirm‑модал для dangerous команд, одинаковый для `cli` и `ibcmd`, с предсказуемой логикой.

#### Scenario: Confirm‑модал открывается только при включении подтверждения
- **GIVEN** команда имеет `risk_level=dangerous` и `confirm_dangerous=false`
- **WHEN** пользователь включает подтверждение dangerous
- **THEN** открывается confirm‑модал с описанием риска и идентификатором команды
- **AND** при Cancel `confirm_dangerous` остаётся `false`
- **AND** при Confirm `confirm_dangerous` становится `true`

### Requirement: Полный рендер common flags `ibcmd` и явное разделение DBMS/IB auth
Система ДОЛЖНА (SHALL) оптимизировать UX отображения общего набора driver-level флагов `ibcmd` так, чтобы:
- секция `Driver options` оставалась управляемой при большом количестве полей;
- “частые” поля были доступны без скролла на несколько экранов;
- редкие/advanced поля не мешали основному сценарию.

#### Scenario: Driver options не превращаются в “простыню”
- **GIVEN** пользователь открыл `DriverCommandBuilder` для `driver=ibcmd`
- **WHEN** UI отображает `Driver options`
- **THEN** поля сгруппированы и доступны через сворачиваемые блоки (минимум: `Auth context`, `Connection`, `Execution`, `Advanced`)
- **AND** по умолчанию показаны только “common” и/или заполненные поля, а “advanced” скрыты до явного действия пользователя

### Requirement: UI ограничивает выбор `ib_auth.strategy=service`
Система ДОЛЖНА (SHALL) отображать и позволять выбрать `ib_auth.strategy=service` только если команда и пользователь удовлетворяют политике allowlist/RBAC.

В противном случае UI ДОЛЖЕН (SHALL) либо:
- скрывать опцию `service`, либо
- показывать её disabled с понятным объяснением (почему недоступно).

#### Scenario: Опция service недоступна для non-allowlist или dangerous команды
- **GIVEN** команда вне allowlist или `risk_level=dangerous`
- **WHEN** пользователь открывает `DriverCommandBuilder`
- **THEN** `ib_auth.strategy=service` недоступна в UI

### Requirement: DBMS креды не вводятся в DriverCommandBuilder
Система ДОЛЖНА (SHALL) не отображать в `DriverCommandBuilder` поля для DBMS кредов (`connection.offline.db_user/db_pwd`) и не позволять вводить/сохранять их в UI state/shortcuts.

#### Scenario: DBMS креды скрыты и помечены как “resolved”
- **GIVEN** пользователь открыл `DriverCommandBuilder` для `driver=ibcmd`
- **WHEN** UI отображает `Driver options`
- **THEN** `connection.offline.db_user` и `connection.offline.db_pwd` не отображаются как поля ввода
- **AND** UI показывает подсказку, что DBMS креды резолвятся через credential mapping/секреты

### Requirement: Shortcuts сохраняют воспроизводимую конфигурацию команды
Система ДОЛЖНА (SHALL) сохранять ярлык `ibcmd` так, чтобы он воспроизводил выбранную конфигурацию команды, включая:
- `command_id`
- `driver options` (connection/timeout/ib_auth.strategy/auth_database_id, без секретов)
- `params`
- `additional_args` (или эквивалентное поле ввода `args_text`)

#### Scenario: Save shortcut включает driver options/params/args
- **GIVEN** пользователь настроил `DriverCommandBuilder` для `driver=ibcmd`
- **WHEN** пользователь нажимает `Save shortcut`
- **THEN** ярлык при последующей загрузке восстанавливает `command_id`, `driver options`, `params` и `additional_args`

### Requirement: Configure для `ibcmd` явно применяется к выбранным таргетам
Система ДОЛЖНА (SHALL) обеспечивать, что конфигурация из шага Configure применяется к набору выбранных баз (Target step):
- для `scope=per_database` одна операция создаёт N задач (по одной на базу);
- UI показывает, что часть параметров берётся “per target” (например `db_name`) и будет различаться для выбранных баз.

#### Scenario: Пользователь выбрал N баз и настраивает одну конфигурацию
- **GIVEN** пользователь выбрал N баз в Target step (N > 1)
- **WHEN** пользователь заполняет Configure для `driver=ibcmd`
- **THEN** UI показывает, что конфигурация применяется ко всем выбранным базам
- **AND** UI показывает, какие driver options будут резолвиться per target (минимум `db_name`)

### Requirement: Shortcuts валидируются при изменении схемы
Система ДОЛЖНА (SHALL) валидировать загружаемый ярлык относительно текущей effective schema и предпринимать действие, если схема изменилась:
- показать пользователю, какие поля устарели/неизвестны/некорректны;
- предложить автоматическую нормализацию (drop неизвестных полей, применение defaults) или ручное исправление.

#### Scenario: Загрузка ярлыка с устаревшими полями
- **GIVEN** ярлык был сохранён до изменения `driver_schema`/`command schema`
- **WHEN** пользователь загружает ярлык
- **THEN** UI показывает предупреждение о несовместимости
- **AND** UI предлагает “Apply migrated config” или перейти к ручному редактированию

### Requirement: UI показывает actionable ошибку при отсутствии offline DBMS metadata
Система ДОЛЖНА (SHALL) отображать понятную и actionable ошибку, если запуск `ibcmd_cli` в `connection.offline` невозможен из-за отсутствующих DBMS metadata (`dbms/db_server/db_name`) у части выбранных баз.

UI ДОЛЖЕН (SHALL):
- показать пользователю, какие поля отсутствуют (без секретов),
- подсказать, что часть значений можно задать в Configure (общие), а часть может требоваться per target (например `db_name`),
- подсказать, где именно исправить DBMS metadata (например, на экране `/databases` через UI редактирования DBMS metadata),
- не начинать выполнение/не показывать “queued” при таком отказе.

#### Scenario: Ошибка показывает список баз и missing keys
- **GIVEN** пользователь запускает `ibcmd_cli` с `connection.offline`
- **AND** API возвращает `error.code=OFFLINE_DB_METADATA_NOT_CONFIGURED` и список проблемных таргетов
- **WHEN** UI отображает результат
- **THEN** UI показывает ошибку и список проблемных баз (ограниченно) и missing keys
- **AND** UI не сохраняет/не отображает секретные значения

#### Scenario: UI подсказывает путь исправления (через /databases)
- **GIVEN** API вернул `error.code=OFFLINE_DB_METADATA_NOT_CONFIGURED`
- **WHEN** UI отображает ошибку
- **THEN** UI содержит подсказку “заполните DBMS metadata базы на /databases” (или эквивалентный CTA)

### Requirement: Connection по умолчанию берётся из профиля базы и допускает per-run override
Система ДОЛЖНА (SHALL) в UI запуска `ibcmd` (DriverCommandBuilder/мастер операций) использовать профиль подключения базы как источник connection по умолчанию для `scope=per_database`.

Профиль базы трактуется как “raw flags” и может включать:
- `remote` (SSH URL),
- `pid`,
- `offline.*`.

UI ДОЛЖЕН (SHALL):
- отображать derived connection, резолвленный per target из профилей выбранных баз,
- поддерживать per-run override connection (применяемый ко всем выбранным базам),
- корректно отображать mixed mode (если разные базы используют разные заполненные параметры),
- отображать `remote` как SSH URL (а не HTTP).

#### Scenario: Mixed mode отображается явно на основе заполненных полей
- **GIVEN** пользователь выбрал N баз с разными профилями (например, у части задан `remote`, у части `offline`)
- **WHEN** UI отображает секцию Connection
- **THEN** UI показывает, что connection будет отличаться per target (mixed mode)

### Requirement: Derived connection показывает summary+diff для `ibcmd` per_database
Система ДОЛЖНА (SHALL) в UI `DriverCommandBuilder` для `driver=ibcmd` и `scope=per_database`, когда override connection отключён, показывать:
- аггрегированную сводку derived connection (counts по effective mode, mixed mode);
- diff по ключам connection, которые отличаются между выбранными базами.

UI НЕ ДОЛЖЕН (SHALL NOT) отображать или запрашивать секреты (пароли и т.п.) в этой сводке/diff.

#### Scenario: Mixed mode отображается как сводка и diff
- **GIVEN** выбрано несколько баз, часть с `mode=remote`, часть с `mode=offline`
- **WHEN** пользователь открывает Configure/Driver options для `ibcmd` per_database без override
- **THEN** UI показывает сводку (remote_count/offline_count, mixed_mode=true)
- **AND** UI показывает diff по ключам, где значения отличаются между таргетами (например `remote_url`, `offline.config`, `offline.data`, `offline.db_name`)

#### Scenario: Все таргеты remote с одинаковым URL не создают “лишний diff”
- **GIVEN** выбрано N баз с effective mode `remote` и одинаковым `remote_url`
- **WHEN** UI показывает derived connection
- **THEN** UI показывает summary
- **AND** diff не содержит строку `remote_url` как отличающийся ключ

