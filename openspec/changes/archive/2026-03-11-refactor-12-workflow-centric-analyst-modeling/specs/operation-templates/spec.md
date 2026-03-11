## ADDED Requirements
### Requirement: Templates MUST оставаться каталогом атомарных операций
Система ДОЛЖНА (SHALL) использовать `/templates` как catalog of atomic execution building blocks и НЕ ДОЛЖНА (SHALL NOT) использовать templates как primary analyst-facing surface для моделирования схем распределения или публикации.

Если система сохраняет `workflow` как executor kind template, этот режим ДОЛЖЕН (SHALL) быть явно помечен как compatibility/integration path, а не как рекомендуемый путь для analyst-authored process composition.

#### Scenario: Analyst создает схему в `/workflows`, а не в `/templates`
- **GIVEN** аналитик хочет описать новую схему распределения
- **WHEN** он использует analyst-facing surfaces системы
- **THEN** схема создаётся как workflow definition
- **AND** `/templates` используется только для выбора атомарных операций, из которых workflow собирает шаги

### Requirement: Templates MUST публиковать явный execution contract для workflow nodes
Система ДОЛЖНА (SHALL) публиковать для templates explicit execution contract, пригодный для analyst-friendly workflow authoring:
- capability;
- input/output contract;
- side-effect profile;
- binding provenance.

Workflow editor ДОЛЖЕН (SHALL) использовать этот contract при выборе template для operation node.

#### Scenario: Workflow editor показывает contract выбранного template
- **GIVEN** аналитик выбирает template для operation node
- **WHEN** editor загружает metadata template
- **THEN** пользователь видит capability, input/output contract и side-effect summary
- **AND** editor использует эти данные для валидации настройки шага
