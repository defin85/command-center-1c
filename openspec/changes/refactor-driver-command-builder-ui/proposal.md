# Change: Унификация UI для schema-driven CLI (Designer CLI + IBCMD CLI)

## Why
В нескольких местах UI используется `DriverCommandBuilder` для конфигурирования schema-driven операций:
- `designer_cli` (driver=`cli`)
- `ibcmd_cli` (driver=`ibcmd`)

Сейчас пользовательский опыт заметно различается, несмотря на общий компонент. Это:
- усложняет обучение и повышает когнитивную нагрузку;
- увеличивает риск ошибок (особенно для dangerous команд);
- усложняет поддержку, потому что часть логики execution context “вшита” в UI, а не описана как driver schema;
- делает `auth_database_id` неочевидным (часто воспринимается как “ещё один таргет”, хотя по смыслу это RBAC + маппинг пользователя CC ↔ infobase user).

## What Changes
- Унифицировать структуру формы `DriverCommandBuilder` для `cli` и `ibcmd` **во всех местах использования**.
- Сохранить текущий язык UI (EN) и минимальный/безопасный объём UX-изменений.
- Расширить `driver_schema`, чтобы driver-level execution context (например `connection.*`, offline‑поля, timeout, stdin, auth context) и `cli_options.*` описывались схемой и рендерились единообразно.
- `auth_database_id` формализовать как **auth context** (RBAC + маппинг пользователя), а не как таргет выполнения.
- Dangerous confirmation оставить через confirm‑модал, но сделать его **единым и предсказуемым**:
  - модал открывается только при попытке включить подтверждение;
  - Cancel не меняет состояние;
  - содержимое и кнопки одинаковы для `cli` и `ibcmd`.

## Impact
- Затронутые спеки: `command-schemas-driver-options` (modified), `ui-driver-command-builder` (new)
- Затронутый UI: все страницы/компоненты, использующие `DriverCommandBuilder` (операции, templates, и т.п.)
- Ожидаемый эффект: одинаковая модель взаимодействия для `designer_cli` и `ibcmd_cli`, меньше ошибок при dangerous командах, более “схемное” описание execution context
- Ломающих изменений не планируется; изменения направлены на унификацию UI и уточнение контракта driver schema/auth context
