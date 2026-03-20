## ADDED Requirements
### Requirement: `/pools/templates` MUST использовать canonical schema template workspace
Система ДОЛЖНА (SHALL) представлять `/pools/templates` как schema template workspace с route-addressable selected template/filter context и canonical secondary authoring surfaces для create/edit flows.

#### Scenario: Schema template workspace восстанавливает selected template из URL
- **GIVEN** оператор открывает `/pools/templates` с query state, указывающим активные фильтры и выбранный schema template
- **WHEN** страница перезагружается или открывается по deep-link
- **THEN** workspace восстанавливает тот же template context
- **AND** edit/create flow остаётся внутри canonical secondary surface без bespoke page-level modal orchestration как единственного пути
