# Спецификация: extensions-overview

## Purpose
Определяет обзорный экран `/extensions` и связанные API/снимки (snapshots) для отображения агрегированной картины расширений по доступным пользователю базам, включая drill-down и требования RBAC.
## Requirements
### Requirement: Обзор расширений по всем базам
Система ДОЛЖНА (SHALL) предоставить экран `/extensions`, который показывает агрегированную таблицу расширений по доступным пользователю базам.

#### Scenario: UI позволяет selective apply flags policy
- **WHEN** пользователь открывает drawer расширения `X` на `/extensions` и нажимает `Apply flags policy`
- **THEN** UI отображает форму из 3 строк (`active`, `safe_mode`, `unsafe_action_protection`), где каждая строка имеет:
  - checkbox “Apply this flag”
  - switch “Value” (disabled, если checkbox выключен)
- **AND** пользователь может подтвердить apply, выбрав подмножество флагов

### Requirement: Нормализованный список расширений в snapshot
Система ДОЛЖНА (SHALL) сохранять в snapshot расширений нормализованный структурированный список расширений, пригодный для табличного отображения и канонизации.

#### Scenario: Snapshot содержит структурированный список
- **WHEN** выполняется настроенное действие list/sync расширений и snapshot обновляется
- **THEN** `DatabaseExtensionsSnapshot.snapshot` содержит `extensions` (массив объектов расширений), где для каждого элемента:
  - **SHALL** присутствовать `name`
  - **MAY** присутствовать `purpose`
  - **MAY** присутствовать `is_active`
  - **MAY** присутствовать `safe_mode`
  - **MAY** присутствовать `unsafe_action_protection`

### Requirement: Drill-down до списка баз
Система ДОЛЖНА (SHALL) позволять пользователю перейти от расширения к списку баз, где оно установлено/включено/отсутствует.

#### Scenario: Пользователь открывает детали расширения
- **WHEN** пользователь выбирает расширение в таблице `/extensions`
- **THEN** UI отображает список баз (доступных пользователю) и статус выбранного расширения в каждой базе

### Requirement: Фильтрация и поиск
Система ДОЛЖНА (SHALL) поддерживать фильтрацию обзорного списка по статусу расширения, версии (если доступны) и по базе (опционально).

#### Scenario: Фильтр по базе не ломает агрегацию флагов
- **GIVEN** пользователь имеет доступ к базе `database_id`
- **WHEN** пользователь открывает `/extensions` с `database_id=...`
- **THEN** API ограничивает *набор имён расширений в выдаче* теми, которые присутствуют в snapshot выбранной базы
- **AND** агрегаты и унифицированные агрегаты флагов по этим расширениям продолжают считаться по всем доступным пользователю базам (как без фильтра)

### Requirement: RBAC фильтрация по доступным базам
Система ДОЛЖНА (SHALL) возвращать в overview/drill-down только данные по базам, к которым у пользователя есть доступ.

#### Scenario: Пользователь не видит чужие базы
- **WHEN** пользователь запрашивает aggregated overview или drill-down
- **THEN** в ответе отсутствуют базы и агрегаты, относящиеся к базам без разрешения `view_database`

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

### Requirement: Workflow-first bulk управление флагами и расширениями
Система ДОЛЖНА (SHALL) использовать workflow-first сценарий как основной способ массового управления расширениями/флагами в `/extensions`.

#### Scenario: Bulk apply запускает workflow rollout
- **GIVEN** пользователь работает в `/extensions` и выбирает массовое применение
- **WHEN** пользователь подтверждает параметры (`flags_values`, `apply_mask`, таргеты, rollout strategy)
- **THEN** UI запускает workflow execution
- **AND** дальнейший прогресс отслеживается через `/operations`

### Requirement: Точечное управление остаётся fallback-режимом
Система ДОЛЖНА (SHALL) сохранять точечное применение (single/small target) как fallback и НЕ ДОЛЖНА (SHALL NOT) позиционировать его как основной путь массового rollout.

#### Scenario: Оператор применяет изменения для одной базы
- **GIVEN** оператору нужен аварийный/индивидуальный случай
- **WHEN** он запускает точечное применение для одной базы
- **THEN** UI использует тот же валидируемый execution pipeline
- **AND** интерфейс явно маркирует режим как fallback/аварийный

