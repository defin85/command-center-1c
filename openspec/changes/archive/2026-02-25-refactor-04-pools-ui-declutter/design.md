## Context
Операторские страницы Pools накопили несколько самостоятельных workflows в рамках одного длинного экрана. Это приводит к высокой когнитивной нагрузке: пользователь вынужден одновременно обрабатывать множество таблиц, форм, action-кнопок и diagnostic JSON-блоков.

Ключевая проблема не в отсутствии функций, а в недостаточной информационной иерархии.

Дополнительный контекст: часть diagnostics UX должна опираться на расширенный runtime observability contract из `refactor-03-unify-platform-execution-runtime`. Без sequencing возрастает риск повторных UI переделок.

## Goals / Non-Goals
- Goals:
  - Снизить когнитивную нагрузку на `/pools/catalog` и `/pools/runs` через task-oriented структуру.
  - Сохранить все существующие доменные операции без потери функциональности.
  - Добавить отсутствующий edit-flow шаблонов на `/pools/templates`.
  - Повысить операторскую предсказуемость: «один экран = один этап задачи».
- Non-Goals:
  - Не менять бизнес-правила run lifecycle/topology validation.
  - Не делать глобальный redesign навигации приложения.
  - Не вводить новый runtime/API для распределения.

## Decisions
### Decision 1: Task-oriented IA вместо «всё на одной странице»
Для `/pools/catalog` и `/pools/runs` вводится логическое разделение на рабочие зоны (tabs/segmented sections). Каждая зона показывает только релевантные controls и данные текущего этапа.

### Decision 2: Progressive disclosure для advanced данных
Тяжёлые JSON/diagnostics блоки не показываются по умолчанию. Они доступны через явное действие (`Advanced`, `Diagnostics`, `Show JSON`) без потери данных и контекста.

### Decision 3: Единый контекст выбора сущности
Выбранный `pool` и `run` остаётся единым контекстом страницы, чтобы пользователь не повторял выбор в каждом блоке. Это уменьшает дублирование селекторов и риск ошибок оператора.

### Decision 4: `/pools/templates` как полноценный CRUD-lite для шаблонов
Страница шаблонов использует уже введённый edit-flow: выбор строки -> modal prefill -> save/update. В рамках данного change это baseline, который ДОЛЖЕН (SHALL) сохранить работоспособность после UI-declutter.

### Decision 5: Двухтрековое внедрение UI с зависимостью от runtime-контрактов
Реализация разделяется на:
- Track UI-A (independent): IA declutter + stage/task flow + progressive disclosure.
- Track UI-B (dependent): финальная интеграция diagnostics представления на стабилизированных полях `root_operation_id`, `execution_consumer`, `lane` из `refactor-03`.

Track UI-B стартует только после готовности OpenAPI/client contracts из `refactor-03`.

## Trade-offs
- Плюс: меньше визуального шума, проще onboarding операторов, быстрее выполнение типовых сценариев.
- Минус: пользователю может потребоваться дополнительный клик для доступа к advanced блокам.
- Компромисс: сохранить быстрый доступ к advanced через явные и заметные toggles, без скрытия критичных статусов.

## UX Acceptance Criteria (design-level)
- На `/pools/catalog` оператор может выполнить создание/редактирование организации без одновременного шума topology/editor блоков.
- На `/pools/runs` оператор может создать run и отдельно перейти к inspect/safe/retry без прокрутки через весь контент.
- На `/pools/templates` оператор может изменить существующий шаблон без ручного внешнего API-клиента.
- Advanced JSON/diagnostics отображаются по запросу и не мешают базовому операторскому потоку.

## Risks / Mitigations
- Риск: регрессия скрытых операторских сценариев из-за изменения layout.
  - Mitigation: e2e smoke на ключевые сценарии (create run, safe action, retry, edit template).
- Риск: несоответствие frontend и API по update template.
  - Mitigation: contract update + backend/frontend tests в одном change.
- Риск: потеря discoverability редких функций.
  - Mitigation: явные labels для advanced секций и сохранение контекстных подсказок.
- Риск: интеграция diagnostics UI с нестабильными runtime полями вызовет повторный рефакторинг.
  - Mitigation: зафиксировать blocker Track UI-B до завершения `refactor-03`, использовать временный backward-compatible rendering только на миграционное окно.
