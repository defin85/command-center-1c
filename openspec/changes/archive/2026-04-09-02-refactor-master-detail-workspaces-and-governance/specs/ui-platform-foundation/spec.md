## MODIFIED Requirements
### Requirement: MasterDetail surfaces MUST иметь narrow-viewport fallback без горизонтального overflow
Система ДОЛЖНА (SHALL) обеспечивать, что `MasterDetail` surfaces на узких viewport не зависят от фиксированного dual-column layout как единственного режима отображения.

`MasterDetail` surface ДОЛЖЕН (SHALL) переводить detail/edit в `Drawer`, off-canvas panel или отдельный route/state на narrow viewport и НЕ ДОЛЖЕН (SHALL NOT) допускать horizontal overflow как штатное mobile behaviour.

Для governed catalog/detail routes master pane ДОЛЖЕН (SHALL) оставаться compact selection surface и НЕ ДОЛЖЕН (SHALL NOT) использовать wide data grid как default primary composition path. Широкие таблицы, требующие многих колонок или горизонтального скролла, ДОЛЖНЫ (SHALL) жить в detail pane, dedicated secondary surface или explicit full-width workspace, если это оправдано самим операторским сценарием.

#### Scenario: Mobile-пользователь открывает detail без page-wide horizontal scroll
- **GIVEN** пользователь открывает `MasterDetail` surface на narrow viewport
- **WHEN** он выбирает элемент списка для просмотра detail или edit
- **THEN** detail/edit открывается в mobile-safe fallback режиме (`Drawer`, panel или отдельный route/state)
- **AND** страница не требует page-wide horizontal scroll для работы с основным контентом

#### Scenario: Desktop master pane остаётся compact selection surface
- **GIVEN** оператор открывает governed `MasterDetail` route на desktop viewport
- **WHEN** route показывает primary catalog в master pane
- **THEN** master pane остаётся scan-friendly selection surface с компактной плотностью
- **AND** route не помещает в master pane wide table с horizontal overflow как default primary path
