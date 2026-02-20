## MODIFIED Requirements
### Requirement: Import schemas MUST быть публичными переиспользуемыми шаблонами
Система ДОЛЖНА (SHALL) поддерживать публичные шаблоны схем импорта (XLSX/JSON), доступные для выбора пользователем при запуске run.

Система ДОЛЖНА (SHALL) предоставлять на странице `/pools/templates` operator-facing UI для создания и редактирования шаблонов импорта (`code`, `name`, `format`, `is_public`, `is_active`, `workflow_template_id`, `schema`, `metadata`) без использования внешних HTTP-клиентов.

Система МОЖЕТ (MAY) хранить опциональную привязку шаблона к workflow для повторного использования проверенных схем.

#### Scenario: Пользователь выбирает шаблон при запуске импорта
- **WHEN** пользователь запускает bottom-up run
- **THEN** система предлагает список публичных шаблонов схем
- **AND** выбранный шаблон применяется для разбора входного файла/JSON

#### Scenario: Оператор редактирует существующий шаблон через UI
- **GIVEN** в каталоге шаблонов есть существующий template
- **WHEN** оператор открывает edit-flow на `/pools/templates`, меняет `name`/`schema`/`metadata` и сохраняет
- **THEN** изменения persist'ятся через канонический API update endpoint
- **AND** обновлённые данные отображаются в таблице шаблонов без ручного API-вызова

#### Scenario: Невалидный JSON блокирует сохранение шаблона
- **GIVEN** оператор ввёл невалидный JSON в `schema` или `metadata`
- **WHEN** оператор пытается сохранить шаблон
- **THEN** UI блокирует submit
- **AND** показывает понятную ошибку валидации без потери введённого содержимого

## ADDED Requirements
### Requirement: Pool catalog UI MUST быть организован как task-oriented workspace
Система ДОЛЖНА (SHALL) организовать `/pools/catalog` как набор логических рабочих зон (организации, пулы, topology editing, graph preview), чтобы оператор видел только релевантные controls и данные текущего шага.

Система ДОЛЖНА (SHALL) уменьшить количество одновременно видимых mutating controls и не смешивать независимые сценарии в одном визуальном блоке.

#### Scenario: Оператор управляет организациями без шума topology editor
- **GIVEN** оператор работает в зоне управления организациями на `/pools/catalog`
- **WHEN** оператор выполняет create/edit/sync организаций
- **THEN** интерфейс не требует взаимодействия с controls topology editor
- **AND** контент topology не доминирует в текущем контексте задачи

#### Scenario: Topology editing выполняется в отдельном фокусном контексте
- **GIVEN** оператор переключился к редактированию topology snapshot
- **WHEN** оператор добавляет node/edge и сохраняет snapshot
- **THEN** интерфейс показывает только релевантные topology controls и validation feedback
- **AND** выбранный pool context сохраняется между рабочими зонами

#### Scenario: Advanced metadata поля скрыты по умолчанию
- **GIVEN** оператор открывает topology editor
- **WHEN** он выполняет базовое редактирование структуры
- **THEN** advanced metadata/JSON controls скрыты по умолчанию
- **AND** доступны по явному действию (progressive disclosure)
