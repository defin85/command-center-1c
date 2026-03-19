## ADDED Requirements
### Requirement: `/databases` MUST использовать canonical workspace composition для database management
Система ДОЛЖНА (SHALL) реализовать `/databases` как platform workspace, где database catalog является primary selection context, а metadata management, DBMS metadata, connection profile и extensions/manual-operation actions представлены как dedicated secondary surfaces или явные handoff paths.

Route ДОЛЖЕН (SHALL) сохранять selected database и active management context в URL-addressable state, чтобы reload, deep-link и browser back/forward не сбрасывали operator workspace silently.

Primary edit/inspection flows НЕ ДОЛЖНЫ (SHALL NOT) оставаться набором конкурирующих raw drawers/modals без общего platform shell. Для canonical management path должны использоваться `DrawerFormShell`, `ModalFormShell` или явный route handoff в canonical surface.

#### Scenario: Оператор возвращается к выбранной ИБ и management context после reload
- **GIVEN** оператор открыл конкретную ИБ и metadata management context на `/databases`
- **WHEN** страница перезагружается или оператор использует browser back/forward
- **THEN** UI восстанавливает selected database и активный management context
- **AND** канонический workspace не возвращается молча в общий невыбранный catalog state

#### Scenario: Metadata management не конкурирует с другими raw page-level overlays
- **GIVEN** оператор работает со списком ИБ на `/databases`
- **WHEN** он открывает metadata management, DBMS metadata или connection profile flow
- **THEN** UI использует единый canonical secondary surface pattern или явный handoff
- **AND** оператор не сталкивается с несколькими конкурирующими page-level modal/drawer paradigms внутри одного route
