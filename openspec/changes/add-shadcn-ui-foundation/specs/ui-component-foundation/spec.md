## ADDED Requirements
### Requirement: Frontend MUST поддерживать поэтапное сосуществование текущего UI stack и нового local foundation layer
Система ДОЛЖНА (SHALL) поддерживать migration path, при котором существующие `Ant Design` поверхности и новый project-owned UI foundation layer на базе `shadcn/ui` могут сосуществовать в одном frontend приложении.

Новые или целенаправленно переписываемые UI surfaces ДОЛЖНЫ (SHALL) использовать локальные project-owned primitives как primary path, а не прямые vendor imports как основной способ композиции.

Существующие `Ant Design` поверхности МОГУТ (MAY) оставаться без переписывания до тех пор, пока для них не определены и не подтверждены parity criteria.

#### Scenario: Новый isolated screen использует local UI layer, а legacy экран остаётся на Ant Design
- **GIVEN** в приложении существует legacy backoffice page на `Ant Design`
- **AND** команда добавляет новый isolated screen или целенаправленно переписывает один ограниченный workflow
- **WHEN** новый surface реализуется на обновлённом frontend foundation
- **THEN** он использует локальные project-owned UI primitives
- **AND** legacy `Ant Design` screen продолжает работать без обязательного одновременного rewrite

### Requirement: UI foundation migration MUST идти по vertical slices, а не через big-bang rewrite
Система ДОЛЖНА (SHALL) выполнять migration на новый UI foundation по incremental vertical slices с явными readiness gates.

CRUD-heavy или admin-heavy поверхности с плотными таблицами, сложными формами, drawer/modal workflows и высокой зависимостью от текущих `Ant Design` interaction patterns НЕ ДОЛЖНЫ (SHALL NOT) быть первыми обязательными кандидатами на migration без заранее подтверждённой parity.

#### Scenario: Первый pilot выбирается среди low-risk поверхностей
- **GIVEN** команда начинает migration на новый UI foundation
- **WHEN** выбирается initial pilot
- **THEN** pilot берётся из low-risk или isolated surface
- **AND** migration не требует немедленного rewrite всех сложных admin-heavy страниц

### Requirement: Shared design tokens and layout primitives MUST быть централизованы в локальном UI layer
Система ДОЛЖНА (SHALL) централизовать базовые visual tokens и layout/text primitives внутри project-owned UI layer, чтобы mixed-mode migration не приводила к произвольному визуальному дрейфу между legacy и migrated surfaces.

Feature code НЕ ДОЛЖЕН (SHALL NOT) определять собственные несогласованные наборы spacing/color/typography conventions как primary path для новых migrated surfaces.

#### Scenario: Mixed-mode приложение сохраняет согласованную визуальную семантику
- **GIVEN** часть экранов уже использует новый local UI foundation, а часть ещё остаётся на `Ant Design`
- **WHEN** пользователь переходит между этими экранами
- **THEN** базовые visual semantics определяются централизованными tokens и layout primitives
- **AND** migration не создаёт неконтролируемый визуальный разнобой

### Requirement: Migration readiness MUST учитывать accessibility, operational parity и testability
Система ДОЛЖНА (SHALL) считать surface готовым к migration только при подтверждённой parity по accessibility, keyboard navigation, confirm/destructive flows и automated testability.

Система НЕ ДОЛЖНА (SHALL NOT) считать migration успешной только по факту визуального совпадения без проверки behavioural parity.

#### Scenario: Surface не переводится на новый foundation без behavioural parity
- **GIVEN** команда оценивает кандидат на migration
- **WHEN** surface не демонстрирует достаточную parity по accessibility, keyboard behavior или confirm/destructive interactions
- **THEN** migration этого surface откладывается
- **AND** legacy implementation остаётся допустимым runtime path до устранения разрыва
