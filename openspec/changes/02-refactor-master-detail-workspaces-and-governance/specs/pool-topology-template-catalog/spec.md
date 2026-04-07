## MODIFIED Requirements
### Requirement: `/pools/topology-templates` MUST использовать platform-first workspace composition
Система ДОЛЖНА (SHALL) реализовать `/pools/topology-templates` как platform workspace с list/detail navigation и mobile-safe fallback для detail/edit surface.

Primary authoring flows НЕ ДОЛЖНЫ (SHALL NOT) строиться как ad-hoc page-level canvas без platform primitives.

Desktop master pane ДОЛЖЕН (SHALL) оставаться compact reusable template catalog и не должен превращаться в wide table-first workspace. Detail pane ДОЛЖЕН (SHALL) быть owner-ом revision lineage, structural summary и authoring entry points.

Operator guidance МОЖЕТ (MAY) присутствовать в route, но НЕ ДОЛЖНА (SHALL NOT) доминировать над catalog/detail workspace настолько, чтобы основной reusable selection flow терял первый экран или уступал место oversized instructional chrome.

#### Scenario: Narrow viewport не ломает reusable topology template authoring
- **GIVEN** оператор открывает `/pools/topology-templates` на narrow viewport
- **WHEN** он выбирает template detail или открывает create/revise flow
- **THEN** detail/edit surface использует mobile-safe fallback
- **AND** рабочий сценарий не требует page-wide horizontal overflow как штатного режима

#### Scenario: Desktop route показывает compact catalog вместо compressed grid
- **GIVEN** оператор открывает `/pools/topology-templates` на desktop viewport
- **WHEN** он выбирает reusable topology template
- **THEN** master pane остаётся compact selection catalog
- **AND** revision/history/structure inspection живут в detail pane, а не в wide table-first master canvas
