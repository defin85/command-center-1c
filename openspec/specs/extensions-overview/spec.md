# Спецификация: extensions-overview

## Purpose
Определяет обзорный экран `/extensions` и связанные API/снимки (snapshots) для отображения агрегированной картины расширений по доступным пользователю базам, включая drill-down и требования RBAC.
## Requirements
### Requirement: Обзор расширений по всем базам
Система ДОЛЖНА (SHALL) использовать `/extensions` как templates-only manual operations экран для домена extensions.

#### Scenario: Ручная операция запускается через manual-operation контракт
- **GIVEN** пользователь открыл drawer расширения на `/extensions`
- **WHEN** выбирает `manual_operation`, template и подтверждает запуск
- **THEN** UI вызывает template-based `extensions plan/apply`
- **AND** backend резолвит executor через template contract

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

### Requirement: `/extensions` MUST поддерживать preferred template bindings
Система ДОЛЖНА (SHALL) использовать tenant preferred template binding per manual operation.

#### Scenario: UI подставляет preferred template по умолчанию
- **GIVEN** для `manual_operation="extensions.sync"` настроен preferred template
- **WHEN** пользователь открывает запуск операции
- **THEN** UI подставляет этот template по умолчанию
- **AND** пользователь может переопределить template для конкретного запуска

### Requirement: Preferred template bindings MUST иметь явный read/write API контракт
Система ДОЛЖНА (SHALL) предоставлять tenant-scoped API для управления preferred template bindings:
- `GET /api/v2/extensions/manual-operation-bindings/`,
- `PUT /api/v2/extensions/manual-operation-bindings/{manual_operation}/`,
- `DELETE /api/v2/extensions/manual-operation-bindings/{manual_operation}/`.

#### Scenario: PUT binding с несовместимым template отклоняется
- **WHEN** клиент вызывает `PUT /api/v2/extensions/manual-operation-bindings/{manual_operation}/` с `template_id`, несовместимым с `manual_operation`
- **THEN** backend возвращает `HTTP 400` (`CONFIGURATION_ERROR`)
- **AND** persisted binding не изменяется

#### Scenario: DELETE binding удаляет fallback
- **GIVEN** для `manual_operation` существовал preferred binding
- **WHEN** клиент вызывает `DELETE /api/v2/extensions/manual-operation-bindings/{manual_operation}/`
- **THEN** binding удаляется
- **AND** следующий запуск без `template_id` override завершается `MISSING_TEMPLATE_BINDING`

### Requirement: `/databases` MUST запускать extensions manual operations напрямую
Система ДОЛЖНА (SHALL) позволять запуск manual operations домена extensions прямо из `/databases`, используя тот же backend контракт, что и `/extensions`.

#### Scenario: Запуск из `/databases` использует единый pipeline
- **WHEN** пользователь запускает extensions manual operation из `/databases`
- **THEN** UI вызывает тот же `extensions plan/apply` flow
- **AND** action-catalog path не используется

### Requirement: Action-catalog runtime controls MUST отсутствовать
Система НЕ ДОЛЖНА (SHALL NOT) отображать action-catalog controls на `/extensions` и `/databases`.

#### Scenario: UI не показывает action-catalog controls
- **WHEN** пользователь открывает controls запуска
- **THEN** отсутствуют selector/alerts/navigation, связанные с Action Catalog
- **AND** доступен только templates/manual operations UX

