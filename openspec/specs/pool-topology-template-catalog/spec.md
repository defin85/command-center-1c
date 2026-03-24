# pool-topology-template-catalog Specification

## Purpose
TBD - created by archiving change add-pool-topology-template-catalog-workspace. Update Purpose after archive.
## Requirements
### Requirement: `/pools/topology-templates` MUST предоставлять dedicated operator-facing topology template catalog
Система ДОЛЖНА (SHALL) предоставлять отдельный route `/pools/topology-templates`, где оператор может просматривать reusable topology templates и их revisions без необходимости использовать прямые API-вызовы или служебные внепродуктовые инструменты.

Route ДОЛЖЕН (SHALL) использовать existing topology template backend surface как canonical source-of-truth и показывать:
- список topology templates;
- detail выбранного template;
- latest revision и historical revisions выбранного template.

#### Scenario: Оператор открывает reusable topology template catalog
- **GIVEN** в tenant уже существуют topology templates
- **WHEN** оператор открывает `/pools/topology-templates`
- **THEN** интерфейс показывает список reusable templates и detail выбранного template
- **AND** оператор может просмотреть latest revision и historical revisions без перехода в raw API tooling

### Requirement: `/pools/topology-templates` MUST поддерживать create и revise flows через canonical form shells
Система ДОЛЖНА (SHALL) позволять оператору:
- создать новый `topology_template` вместе с initial revision;
- создать новую revision для уже существующего template.

Эти mutate flows ДОЛЖНЫ (SHALL) использовать canonical form shells и НЕ ДОЛЖНЫ (SHALL NOT) требовать редактирования raw request payload вне штатного интерфейса как primary path.

#### Scenario: Оператор создаёт новый topology template с initial revision
- **GIVEN** оператору нужна новая reusable topology схема
- **WHEN** он открывает create flow в `/pools/topology-templates` и заполняет code, name, abstract nodes и edges initial revision
- **THEN** система создаёт topology template и initial revision через canonical UI flow
- **AND** новый template становится доступен для дальнейшего выбора в consumer surfaces

#### Scenario: Оператор выпускает новую revision существующего topology template
- **GIVEN** в catalog уже существует topology template
- **WHEN** оператор выбирает template и запускает revise flow
- **THEN** интерфейс создаёт новую revision reusable graph
- **AND** existing template остаётся тем же reusable resource, а новая revision появляется в lineage этого template

### Requirement: `/pools/topology-templates` MUST использовать platform-first workspace composition
Система ДОЛЖНА (SHALL) реализовать `/pools/topology-templates` как platform workspace с list/detail navigation и mobile-safe fallback для detail/edit surface.

Primary authoring flows НЕ ДОЛЖНЫ (SHALL NOT) строиться как ad-hoc page-level canvas без platform primitives.

#### Scenario: Narrow viewport не ломает reusable topology template authoring
- **GIVEN** оператор открывает `/pools/topology-templates` на narrow viewport
- **WHEN** он выбирает template detail или открывает create/revise flow
- **THEN** detail/edit surface использует mobile-safe fallback
- **AND** рабочий сценарий не требует page-wide horizontal overflow как штатного режима

