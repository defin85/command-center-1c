# ui-frontend-governance Specification

## Purpose
TBD - created by archiving change refactor-ui-platform-on-ant. Update Purpose after archive.
## Requirements
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

### Requirement: Frontend validation gate MUST fail build/CI при нарушении UI governance rules
Система ДОЛЖНА (SHALL) включать `npm run lint` и связанные UI governance checks в blocking frontend validation gate, который выполняется до принятия изменения.

Если UI governance rules нарушены, route inventory расходится с route map, или monitored surface остаётся без classification, build/CI НЕ ДОЛЖЕН (SHALL NOT) считаться успешным.

#### Scenario: Нарушение lint-правил блокирует validation gate
- **GIVEN** change нарушает UI governance lint rules
- **WHEN** запускается project-defined frontend validation gate
- **THEN** validation gate завершается ошибкой
- **AND** изменение не может быть принято как готовое без исправления

#### Scenario: Drift между route map и governance inventory блокирует validation gate
- **GIVEN** checked-in route map и governance inventory расходятся
- **WHEN** запускается project-defined frontend validation gate
- **THEN** automated governance check сообщает явную причину drift
- **AND** изменение не может заявлять repo-wide governance coverage до синхронизации inventory

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

### Requirement: Репозиторий MUST содержать явный UI platform contract в AGENTS.md
Система ДОЛЖНА (SHALL) хранить в `AGENTS.md` отдельный блок UI instructions, описывающий canonical UI stack, approved page patterns, responsive rules, enforcement boundaries и ограничения на competing primary UI foundations.

Этот блок ДОЛЖЕН (SHALL) быть достаточным, чтобы разработчик или агент мог определить допустимый способ реализации новой frontend surface без обращения к устным договорённостям.

#### Scenario: Агент получает из AGENTS.md достаточные UI instructions
- **GIVEN** агент или разработчик начинает работу над новой frontend surface
- **WHEN** он читает `AGENTS.md`
- **THEN** он видит явный UI platform contract с canonical stack и approved patterns
- **AND** не вынужден угадывать, использовать ли raw `antd`, thin design layer или альтернативную UI foundation

### Requirement: Repo-wide shell-backed authoring surfaces MUST использовать generic governance rules независимо от migration wave
Система ДОЛЖНА (SHALL) применять generic governance lint rule ко всем `*Modal.tsx` и `*Drawer.tsx` модулям, которые используют `ModalFormShell` или `DrawerFormShell`, независимо от того, к какой route family относится этот модуль.

Этот rule ДОЛЖЕН (SHALL) блокировать явно запрещённые legacy layout/data/status/disclosure containers внутри shell-backed authoring surface, если они обходят platform shell contract.

Route family НЕ ДОЛЖНА (SHALL NOT) требовать отдельный file-specific rule только для того, чтобы поймать такие shell-level нарушения.

#### Scenario: Новый drawer вне migrated route нарушает shell contract
- **GIVEN** разработчик добавляет новый `DrawerFormShell` module под legacy route family
- **WHEN** модуль импортирует raw `Descriptions`, `Table`, `Tag`, `Tabs`, `Collapse` или другой явно запрещённый legacy container из governance rules
- **THEN** lint сообщает shell governance violation
- **AND** нарушение ловится без добавления bespoke path-specific правила для этой route family

