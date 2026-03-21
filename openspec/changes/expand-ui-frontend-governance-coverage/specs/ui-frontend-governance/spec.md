## MODIFIED Requirements

### Requirement: Frontend UI platform boundaries MUST быть автоматически проверяемы lint-правилами
Система ДОЛЖНА (SHALL) выражать архитектурные границы UI platform через автоматически исполняемые lint-правила и checked-in governance inventory минимум на уровне `frontend/eslint.config.js`, локального lint plugin или эквивалентных repository-local governance checks.

Этот contract ДОЛЖЕН (SHALL) покрывать:
- каждый operator-facing route-entry module, доступный через route map frontend приложения;
- каждый shell-backed authoring surface, использующий `ModalFormShell` или `DrawerFormShell`.

Каждый такой surface ДОЛЖЕН (SHALL) иметь явную governance classification: `platform-governed`, `legacy-monitored` или `excluded`.

Unclassified route/module НЕ ДОЛЖЕН (SHALL NOT) считаться допустимым состоянием репозитория.

Lint-правила ДОЛЖНЫ (SHALL) блокировать как минимум те нарушения, которые могут быть надёжно выражены статически: прямые запрещённые vendor imports, static `antd` context bypasses, обход canonical wrappers/patterns, использование явно запрещённых composition paths и shell-backed authoring violations.

#### Scenario: Новый route entry остаётся без governance classification
- **GIVEN** разработчик или агент добавляет новый operator-facing route в frontend route map
- **WHEN** запускается frontend lint или связанные governance checks
- **THEN** validation сообщает явную ошибку о missing governance classification
- **AND** изменение не считается валидным до тех пор, пока route не получит допустимый governance tier

#### Scenario: Legacy-monitored route остаётся под repo-wide safety monitoring
- **GIVEN** route ещё не переведён на полный platform shell и имеет tier `legacy-monitored`
- **WHEN** разработчик добавляет competing UI foundation, static `Modal.*` path или другой запрещённый repo-wide bypass
- **THEN** lint сообщает явное governance violation
- **AND** legacy status route не считается основанием обходить общий safety contract

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

## ADDED Requirements

### Requirement: Repo-wide shell-backed authoring surfaces MUST использовать generic governance rules независимо от migration wave
Система ДОЛЖНА (SHALL) применять generic governance lint rule ко всем `*Modal.tsx` и `*Drawer.tsx` модулям, которые используют `ModalFormShell` или `DrawerFormShell`, независимо от того, к какой route family относится этот модуль.

Этот rule ДОЛЖЕН (SHALL) блокировать явно запрещённые legacy layout/data/status/disclosure containers внутри shell-backed authoring surface, если они обходят platform shell contract.

Route family НЕ ДОЛЖНА (SHALL NOT) требовать отдельный file-specific rule только для того, чтобы поймать такие shell-level нарушения.

#### Scenario: Новый drawer вне migrated route нарушает shell contract
- **GIVEN** разработчик добавляет новый `DrawerFormShell` module под legacy route family
- **WHEN** модуль импортирует raw `Descriptions`, `Table`, `Tag`, `Tabs`, `Collapse` или другой явно запрещённый legacy container из governance rules
- **THEN** lint сообщает shell governance violation
- **AND** нарушение ловится без добавления bespoke path-specific правила для этой route family
