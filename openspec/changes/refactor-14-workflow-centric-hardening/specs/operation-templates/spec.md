## MODIFIED Requirements
### Requirement: Templates MUST оставаться каталогом атомарных операций
Система ДОЛЖНА (SHALL) использовать `/templates` как catalog of atomic execution building blocks и НЕ ДОЛЖНА (SHALL NOT) использовать templates как primary analyst-facing surface для моделирования схем распределения или публикации.

Если система сохраняет `workflow` как executor kind template, этот режим ДОЛЖЕН (SHALL) быть явно помечен как compatibility/integration path, а не как рекомендуемый путь для analyst-authored process composition.

Shipped `/templates` surface ДОЛЖЕН (SHALL) показывать для workflow executor templates явный compatibility marker/warning и направлять analyst authoring в `/workflows` как primary composition surface.

Default `/templates` path НЕ ДОЛЖЕН (SHALL NOT) представлять workflow executor templates как рекомендуемый или основной путь для новых analyst-authored схем.

#### Scenario: Analyst создает схему в `/workflows`, а не в `/templates`
- **GIVEN** аналитик хочет описать новую схему распределения
- **WHEN** он использует analyst-facing surfaces системы
- **THEN** схема создаётся как workflow definition
- **AND** `/templates` используется только для выбора атомарных операций, из которых workflow собирает шаги

#### Scenario: Workflow executor template в `/templates` помечен как compatibility-only
- **GIVEN** оператор открывает `/templates` и видит template с `executor_kind="workflow"`
- **WHEN** UI рендерит список или editor для такого template
- **THEN** интерфейс показывает явную compatibility/integration маркировку
- **AND** `/workflows` обозначается как primary analyst-facing surface для process composition
