## ADDED Requirements
### Requirement: `/templates` MUST использовать canonical template management workspace
Система ДОЛЖНА (SHALL) представлять `/templates` как template management workspace с route-addressable selected template/filter context и canonical authoring surfaces для create/edit/inspect flows.

#### Scenario: Template workspace восстанавливает selected template context из URL
- **GIVEN** оператор открывает `/templates` с query state, указывающим фильтры и выбранный template
- **WHEN** страница перезагружается или открывается по deep-link
- **THEN** workspace восстанавливает тот же template context
- **AND** primary create/edit flow использует canonical secondary surface внутри platform workspace
