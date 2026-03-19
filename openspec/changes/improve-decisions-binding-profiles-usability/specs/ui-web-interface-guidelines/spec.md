## MODIFIED Requirements
### Requirement: Формы и фильтры имеют label или aria-label
Система ДОЛЖНА (SHALL) обеспечивать, что `Input`, `Select` и прочие form controls имеют связанный label (через `Form.Item label`/`htmlFor`) или `aria-label`.

Placeholder-only имя НЕ ДОЛЖНО (SHALL NOT) считаться достаточным accessible name для shell-level selector, route-level filter или table-toolbar control, если после выбора значения пользователь теряет явное имя поля.

#### Scenario: Фильтры операций имеют доступные имена
- **GIVEN** на странице есть фильтры операций по ID/Workflow/Node
- **WHEN** пользователь использует скринридер
- **THEN** каждый фильтр имеет доступное имя (label или `aria-label`)

#### Scenario: Shell selector сохраняет понятное имя после выбора значения
- **GIVEN** в общем shell есть selector tenant context или другой shared route control
- **WHEN** пользователь уже выбрал значение и возвращается к контролу с клавиатуры или скринридером
- **THEN** control сохраняет устойчивое доступное имя
- **AND** placeholder не является единственным способом понять назначение поля

## ADDED Requirements
### Requirement: Stateful workspace routes MUST синхронизировать primary navigation state с URL
Система ДОЛЖНА (SHALL) обеспечивать, что stateful workspace routes отражают primary filter/selection state в URL, если без этого пользователь теряет адресуемый рабочий контекст.

Для catalog/detail surfaces сюда входят как минимум selected entity, активный filter mode, поисковый запрос и detail-open state, если они меняют основной смысл текущего экрана.

#### Scenario: Пользователь делится ссылкой на конкретный workspace context
- **GIVEN** пользователь выбрал сущность и фильтры в stateful catalog/detail route
- **WHEN** он копирует URL и открывает его в новой вкладке или использует back/forward
- **THEN** система восстанавливает тот же основной workspace context
- **AND** не требует повторно выбирать entity/filter вручную

### Requirement: Master-detail selection MUST использовать semantic control и явный selected state
Система ДОЛЖНА (SHALL) обеспечивать, что primary selection в master-detail surface выполняется через semantic interactive control, а выбранное состояние читается и визуально, и программно.

Row click без отдельного semantic trigger МОЖЕТ (MAY) существовать как дополнительное удобство, но НЕ ДОЛЖЕН (SHALL NOT) быть единственным primary path.

#### Scenario: Выбор элемента каталога доступен с клавиатуры и имеет selected state
- **GIVEN** пользователь работает с catalog/detail page
- **WHEN** он выбирает элемент списка только с клавиатуры
- **THEN** selection trigger является semantic control
- **AND** текущий выбранный элемент имеет явный selected state (`aria-selected`, `aria-current` или эквивалентный корректный путь)
- **AND** визуальное выделение выбранного элемента читается без наведения мышью
