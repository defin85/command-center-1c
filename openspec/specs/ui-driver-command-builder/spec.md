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
