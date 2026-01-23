# Дизайн: унификация DriverCommandBuilder (cli + ibcmd)

## Цель дизайна
Сделать `DriverCommandBuilder` единой “формой конфигурации команды”, где различия между `cli` и `ibcmd` выражены через driver schema и небольшие driver‑специфичные надстройки (например shortcuts), а не через два разных UX‑пути.

## Текущее состояние (наблюдение)
`DriverCommandBuilder` уже общий, но:
- `cli` driver: имеет отдельный блок `Startup options`/`Logging`.
- `ibcmd` driver: имеет отдельный блок `Connection`/`Offline`/`Timeout`/`Stdin`/`Auth database`, который “вшит” в UI.
- Dangerous confirmation: чекбокс вызывает `modal.confirm()` и создаёт stacked modal поверх wizard‑modal; поведение не всегда очевидно и трудно тестируется.

## Предлагаемая модель

### 1) Driver schema как источник правды для driver-level опций
Расширяем `driver_schema` так, чтобы она описывала:
- driver-level поля (например `connection.remote`, `connection.pid`, `connection.offline.*`, `timeout_seconds`, `stdin`, а также `cli_options.*`).
- UI‑метаданные: группировка в секции и порядок отображения.

Идея: `DriverCommandBuilder` получает (а) выбранную команду (command-level schema) и (б) driver_schema, и рендерит:
- Command selector + описание/источник
- Guided/Manual
- Command params (guided) или args editor (manual)
- Driver options (по driver_schema)
- Preview (канонический argv_masked / маскированный stdin)

### 2) Унификация “execution context”
В UI используем одинаковый паттерн секций:
1. **Command**
2. **Mode** (Guided/Manual)
3. **Parameters** (guided params) / **Extra arguments** (manual)
4. **Driver options** (из driver_schema)
5. **Preview**
6. **Risk / Safety** (dangerous gating)

Для `ibcmd` “Connection/Offline/Timeout/Stdin” становятся частью **Driver options** и получают единый вид и правила валидации/disabled.

### 3) Auth context вместо “Auth database”
Переопределяем смысл `auth_database_id`:
- Это **не таргет выполнения**.
- Это ссылка на infobase, используемая для:
  - RBAC‑проверки (пользователь имеет право OPERATE),
  - маппинга пользователя CommandCenter ↔ infobase user (для схем, где это необходимо).

UI:
- переименовать и объяснять как “Auth mapping infobase” (EN),
- options формируются из **selected targets** (всегда под RBAC),
- для `ibcmd` global scope: поле обязательно, по умолчанию берётся первая выбранная база (детерминированно).

Backend/API:
- валидирует `auth_database_id` как “должна входить в доступный контекст и быть разрешённой по RBAC”.

### 4) Dangerous confirmation: единая политика
Требование: оставить confirm‑модал, но сделать его предсказуемым.

Правила:
- confirm‑модал открывается **только** при включении dangerous‑подтверждения (false → true).
- при Cancel состояние остаётся false.
- модал всегда показывает: risk warning + command label/id + source section (если есть).
- UI не должен открывать несколько stacked modal подряд без явного действия пользователя; confirm для dangerous — единственный такой модал в рамках формы.

## Обратная совместимость
- Внутренние поля конфигурации (`driver_command.*`) сохраняются, но могут получить более строгую структуру/валидацию.
- UI остаётся на EN.

## Открытые вопросы
- Источник options для `auth_database_id`: предлагается строить из `availableDatabaseIds` (контекст UI), но это должно быть формально отражено в схеме как `ui.input_type=database_ref` (options provided by context).
- Согласовать, какие поля относятся к driver schema для `cli` (минимум `cli_options.*`, возможно ещё).

