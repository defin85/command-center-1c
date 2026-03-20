## ADDED Requirements
### Requirement: `/pools/runs` MUST использовать stage-based platform workspace composition
Система ДОЛЖНА (SHALL) реализовать `/pools/runs` как stage-based platform workspace, где create, inspect, safe actions и retry/remediation представлены как явные operator stages с единым selected run context.

Selected run и active stage ДОЛЖНЫ (SHALL) быть URL-addressable и восстанавливаться после reload, deep-link и browser back/forward без повторного ручного выбора run.

Heavy diagnostics ДОЛЖНЫ (SHALL) оставаться progressive disclosure внутри inspect context. Route НЕ ДОЛЖЕН (SHALL NOT) возвращаться к монолитному default canvas, где create form, large diagnostics, safe actions и retry controls одновременно конкурируют как primary content.

На narrow viewport inspect и remediation flows ДОЛЖНЫ (SHALL) использовать mobile-safe secondary surface или route/state fallback без page-wide horizontal overflow.

#### Scenario: Reload сохраняет выбранный run и текущий stage
- **GIVEN** оператор работает с конкретным run на этапе inspect, safe actions или retry
- **WHEN** страница перезагружается или открывается deep-link на этот run
- **THEN** UI восстанавливает selected run и active stage
- **AND** оператор продолжает lifecycle flow без повторного ручного выбора того же run

#### Scenario: Узкий viewport не сводит lifecycle к единому перегруженному полотну
- **GIVEN** оператор открывает `/pools/runs` на narrow viewport
- **WHEN** он переходит между create, inspect и retry/remediation
- **THEN** secondary detail и diagnostics открываются в mobile-safe fallback surface или отдельном stage context
- **AND** основной lifecycle flow остаётся читаемым без page-wide horizontal scroll
