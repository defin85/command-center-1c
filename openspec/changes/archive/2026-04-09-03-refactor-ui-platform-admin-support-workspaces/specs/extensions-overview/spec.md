## ADDED Requirements
### Requirement: `/extensions` MUST использовать canonical management workspace
Система ДОЛЖНА (SHALL) представлять `/extensions` как management workspace с URL-addressable selected extension context, secondary drill-down surface и canonical authoring/remediation shells для template/manual-operation flows.

#### Scenario: Deep-link восстанавливает выбранное расширение и его drill-down
- **GIVEN** оператор открывает `/extensions` с query state, указывающим выбранное расширение и drill-down context
- **WHEN** страница загружается повторно или открывается по deep-link
- **THEN** workspace восстанавливает selected extension context
- **AND** список баз, manual-operation controls и preferred template binding flow открываются как secondary surfaces внутри platform workspace
