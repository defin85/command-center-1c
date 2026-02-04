## MODIFIED Requirements

### Requirement: Обзор расширений по всем базам
Система ДОЛЖНА (SHALL) предоставить экран `/extensions`, который показывает агрегированную таблицу расширений по доступным пользователю базам.

#### Scenario: UI показывает policy-флаги и унифицированные агрегаты
- **WHEN** пользователь открывает `/extensions`
- **THEN** UI отображает список расширений с:
  - агрегатами по базам (`installed/missing/unknown`, версия/дата snapshot),
  - **policy** флагами `active/safe_mode/unsafe_action_protection` как булевыми полями,
  - унифицированными индикаторами состояния/дрейфа для каждого флага (например `mixed`/`unknown` и `drift_count`).

### Requirement: Фильтрация и поиск
Система ДОЛЖНА (SHALL) поддерживать фильтрацию обзорного списка по статусу расширения, версии (если доступны) и по базе (опционально).

#### Scenario: Фильтр по базе не ломает агрегацию флагов
- **GIVEN** пользователь имеет доступ к базе `database_id`
- **WHEN** пользователь открывает `/extensions` с `database_id=...`
- **THEN** API ограничивает *набор имён расширений в выдаче* теми, которые присутствуют в snapshot выбранной базы
- **AND** агрегаты и унифицированные агрегаты флагов по этим расширениям продолжают считаться по всем доступным пользователю базам (как без фильтра)

## ADDED Requirements

### Requirement: Унифицированная агрегация флагов по расширениям
Система ДОЛЖНА (SHALL) возвращать в aggregated overview унифицированную структуру агрегации флагов по каждому расширению для флагов:
`active`, `safe_mode`, `unsafe_action_protection`.

#### Scenario: API возвращает policy+observed+drift для каждого флага
- **GIVEN** для расширения `X` существует policy (частично или полностью)
- **WHEN** пользователь запрашивает `GET /api/v2/extensions/overview/`
- **THEN** каждая строка расширения `X` содержит для каждого флага:
  - `policy` (boolean или null),
  - `observed.true_count/false_count/unknown_count` (по installed subset),
  - `observed.state` (`on|off|mixed|unknown`),
  - `drift_count` (если policy задана).

### Requirement: Drill-down содержит observed значения флагов
Система ДОЛЖНА (SHALL) возвращать в drill-down список баз с observed значениями `active/safe_mode/unsafe_action_protection` (best-effort).

#### Scenario: Drill-down показывает observed флаги per database
- **WHEN** пользователь открывает drawer расширения `X`
- **THEN** UI получает из `GET /api/v2/extensions/overview/databases/` per-db значения флагов
- **AND** для базы без распознанного значения флага UI показывает `unknown` (без подмены на false)
