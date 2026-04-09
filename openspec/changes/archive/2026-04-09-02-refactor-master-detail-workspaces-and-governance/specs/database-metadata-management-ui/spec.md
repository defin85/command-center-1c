## MODIFIED Requirements
### Requirement: `/databases` MUST использовать canonical workspace composition для database management
Система ДОЛЖНА (SHALL) реализовать `/databases` как platform workspace, где database catalog является primary selection context, а metadata management, DBMS metadata, connection profile и extensions/manual-operation actions представлены как dedicated secondary surfaces или явные handoff paths.

Route ДОЛЖЕН (SHALL) сохранять selected database и active management context в URL-addressable state, чтобы reload, deep-link и browser back/forward не сбрасывали operator workspace silently.

Primary edit/inspection flows НЕ ДОЛЖНЫ (SHALL NOT) оставаться набором конкурирующих raw drawers/modals без общего platform shell. Для canonical management path должны использоваться `DrawerFormShell`, `ModalFormShell` или явный route handoff в canonical surface.

Desktop master pane ДОЛЖЕН (SHALL) оставаться compact database catalog, где выбор базы возможен без wide multi-column grid как основного operator path. Rich operational density, bulk-edit heavy controls и metadata-rich tables ДОЛЖНЫ (SHALL) жить в detail/secondary surfaces или включаться по явному operator intent, а не как default master-pane canvas.

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

#### Scenario: Master pane остаётся компактным каталогом баз
- **GIVEN** оператор открывает `/databases` на desktop viewport
- **WHEN** он просматривает и выбирает ИБ в master pane
- **THEN** master pane остаётся компактным catalog/selection surface
- **AND** route не требует wide grid с горизонтальным скроллом как default способ выбора базы
