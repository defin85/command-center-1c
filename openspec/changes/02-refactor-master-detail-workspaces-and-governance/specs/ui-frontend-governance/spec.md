## MODIFIED Requirements
### Requirement: Frontend UI platform boundaries MUST быть автоматически проверяемы lint-правилами
Система ДОЛЖНА (SHALL) выражать архитектурные границы UI platform через автоматически исполняемые lint-правила минимум на уровне `frontend/eslint.config.js` или эквивалентного локального lint plugin.

Lint-правила ДОЛЖНЫ (SHALL) блокировать как минимум те нарушения, которые могут быть надёжно выражены статически: прямые запрещённые vendor imports в новых page surfaces, обход canonical wrappers/patterns и использование явно запрещённых composition paths.

Для governed `MasterDetail` routes lint также ДОЛЖЕН (SHALL):
- блокировать table-first master pane composition, если route использует wide grid или table toolkit как primary selection surface;
- блокировать composition path, который по design зависит от horizontal overflow внутри master pane;
- сообщать route-specific reason, а не generic platform error.

#### Scenario: Запрещённая page-level композиция не проходит lint
- **GIVEN** разработчик или агент добавляет новый UI surface с нарушением platform boundary
- **WHEN** запускается frontend lint
- **THEN** lint сообщает явную ошибку с причиной нарушения
- **AND** изменение не считается валидным до устранения нарушения

#### Scenario: Table-first master pane на governed route блокируется lint
- **GIVEN** route из governance perimeter использует `MasterDetail` layout
- **WHEN** разработчик помещает в master pane wide table или table toolkit как primary catalog
- **THEN** lint сообщает явное нарушение compact master-pane contract
- **AND** изменение не проходит validation gate

### Requirement: Non-lintable UI invariants MUST иметь automated browser-level coverage
Система ДОЛЖНА (SHALL) покрывать automated browser tests те UI invariants, которые нельзя надёжно выразить линтером, включая responsive fallback для `MasterDetail`, отсутствие page-wide horizontal overflow и базовые accessibility contracts.

Для governed `MasterDetail` routes browser-level coverage ДОЛЖНА (SHALL) дополнительно проверять:
- отсутствие pane-level horizontal overflow на canonical desktop/mobile scenarios;
- сохранение readable selection/detail split после reload и deep-link;
- отсутствие misleading empty-state telemetry, если inspect surface показывает zero-task или no-data context.

#### Scenario: Responsive regression ловится browser-level test
- **GIVEN** `MasterDetail` surface имеет mobile fallback contract
- **WHEN** regression возвращает horizontal overflow или ломает mobile detail workflow
- **THEN** automated browser-level test фиксирует нарушение
- **AND** regression не проходит validation gate незамеченной

#### Scenario: Empty inspect regression фиксируется browser-level test
- **GIVEN** operator-facing inspect panel показывает progress или task summary
- **WHEN** regression визуально маркирует zero-task/no-data context как completed state
- **THEN** automated browser-level test фиксирует misleading state
- **AND** validation gate завершается ошибкой до принятия change
