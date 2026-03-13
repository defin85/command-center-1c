## ADDED Requirements
### Requirement: Topology editor MUST hand off metadata maintenance to `/databases`
Система ДОЛЖНА (SHALL) трактовать `/pools/catalog` topology editor как consumer surface для metadata-aware authoring, а не как primary mutate surface для configuration profile или metadata snapshot maintenance.

UI МОЖЕТ (MAY) показывать в builder-контексте readonly indicators текущего metadata state, но НЕ ДОЛЖЕН (SHALL NOT) прятать primary controls `Load metadata`, `Refresh metadata` или эквивалентные metadata maintenance actions внутри edge-policy authoring path как единственный canonical UX.

Если authoring path блокируется из-за отсутствующего/устаревшего metadata context, `/pools/catalog` ДОЛЖЕН (SHALL) направлять оператора в `/databases` для управления configuration profile / metadata snapshot.

#### Scenario: Builder показывает handoff вместо hidden maintenance controls
- **GIVEN** оператор редактирует edge metadata в `/pools/catalog`
- **WHEN** ему нужен metadata maintenance action для выбранной ИБ
- **THEN** UI показывает status и явный handoff в `/databases`
- **AND** primary metadata maintenance control не спрятан внутри topology builder как единственный discoverable path

#### Scenario: Сохранение topology блокируется и направляет в canonical surface
- **GIVEN** topology save отклонён из-за отсутствующего или неактуального metadata context
- **WHEN** UI показывает fail-closed ошибку
- **THEN** сообщение объясняет, что исправление выполняется через `/databases`
- **AND** topology editor не притворяется canonical местом управления snapshot/profile
