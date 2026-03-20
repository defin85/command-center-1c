# ui-frontend-governance Specification

## Purpose
TBD - created by archiving change refactor-ui-platform-on-ant. Update Purpose after archive.
## Requirements
### Requirement: Frontend UI platform boundaries MUST быть автоматически проверяемы lint-правилами
Система ДОЛЖНА (SHALL) выражать архитектурные границы UI platform через автоматически исполняемые lint-правила минимум на уровне `frontend/eslint.config.js` или эквивалентного локального lint plugin.

Lint-правила ДОЛЖНЫ (SHALL) блокировать как минимум те нарушения, которые могут быть надёжно выражены статически: прямые запрещённые vendor imports в новых page surfaces, обход canonical wrappers/patterns и использование явно запрещённых composition paths.

#### Scenario: Запрещённая page-level композиция не проходит lint
- **GIVEN** разработчик или агент добавляет новый UI surface с нарушением platform boundary
- **WHEN** запускается frontend lint
- **THEN** lint сообщает явную ошибку с причиной нарушения
- **AND** изменение не считается валидным до устранения нарушения

### Requirement: Frontend validation gate MUST fail build/CI при нарушении UI governance rules
Система ДОЛЖНА (SHALL) включать `npm run lint` и связанные UI governance checks в blocking frontend validation gate, который выполняется до принятия изменения.

Если UI governance rules нарушены, build/CI НЕ ДОЛЖЕН (SHALL NOT) считаться успешным.

#### Scenario: Нарушение lint-правил блокирует validation gate
- **GIVEN** change нарушает UI governance lint rules
- **WHEN** запускается project-defined frontend validation gate
- **THEN** validation gate завершается ошибкой
- **AND** изменение не может быть принято как готовое без исправления

### Requirement: Non-lintable UI invariants MUST иметь automated browser-level coverage
Система ДОЛЖНА (SHALL) покрывать automated browser tests те UI invariants, которые нельзя надёжно выразить линтером, включая responsive fallback для `MasterDetail`, отсутствие page-wide horizontal overflow и базовые accessibility contracts.

#### Scenario: Responsive regression ловится browser-level test
- **GIVEN** `MasterDetail` surface имеет mobile fallback contract
- **WHEN** regression возвращает horizontal overflow или ломает mobile detail workflow
- **THEN** automated browser-level test фиксирует нарушение
- **AND** regression не проходит validation gate незамеченной

### Requirement: Репозиторий MUST содержать явный UI platform contract в AGENTS.md
Система ДОЛЖНА (SHALL) хранить в `AGENTS.md` отдельный блок UI instructions, описывающий canonical UI stack, approved page patterns, responsive rules, enforcement boundaries и ограничения на competing primary UI foundations.

Этот блок ДОЛЖЕН (SHALL) быть достаточным, чтобы разработчик или агент мог определить допустимый способ реализации новой frontend surface без обращения к устным договорённостям.

#### Scenario: Агент получает из AGENTS.md достаточные UI instructions
- **GIVEN** агент или разработчик начинает работу над новой frontend surface
- **WHEN** он читает `AGENTS.md`
- **THEN** он видит явный UI platform contract с canonical stack и approved patterns
- **AND** не вынужден угадывать, использовать ли raw `antd`, thin design layer или альтернативную UI foundation

