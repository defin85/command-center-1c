## ADDED Requirements
### Requirement: `/operations` MUST использовать task-first platform workspace composition
Система ДОЛЖНА (SHALL) реализовать `/operations` как canonical operational workspace поверх platform layer, где:
- catalog root `BatchOperation` records является primary entry point;
- selected operation detail, timeline и operator actions образуют устойчивый secondary context;
- list/filter, inspect, cancel/action и timeline flows разделены по операторскому намерению, а не свалены в одно page-level полотно;
- selected operation context и active view сохраняются в URL и восстанавливаются после reload/back-forward.

Primary inspect flow НЕ ДОЛЖЕН (SHALL NOT) зависеть от raw full-page modal как единственного пути просмотра детали. На узких viewport detail/timeline ДОЛЖНЫ (SHALL) открываться через mobile-safe secondary surface (`Drawer`, panel или эквивалентный route/state fallback) без page-wide horizontal overflow.

#### Scenario: Выбранная операция восстанавливается из URL без повторного ручного выбора
- **GIVEN** оператор открывает `/operations` с query state выбранной root operation
- **WHEN** страница загружается заново или пользователь возвращается через browser back/forward
- **THEN** UI восстанавливает selected operation и active inspect context
- **AND** оператору не нужно заново искать ту же запись в catalog

#### Scenario: Узкий viewport сохраняет inspect flow без монолитного canvas
- **GIVEN** оператор работает с `/operations` на narrow viewport
- **WHEN** он открывает detail или timeline выбранной операции
- **THEN** secondary context открывается в mobile-safe fallback surface
- **AND** основной list/action flow остаётся доступным без page-wide horizontal scroll
