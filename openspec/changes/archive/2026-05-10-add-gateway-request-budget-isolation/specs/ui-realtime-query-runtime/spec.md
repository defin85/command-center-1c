## ADDED Requirements

### Requirement: Shell bootstrap and heavy background routes MUST preserve request-budget isolation across shared user sessions
Система ДОЛЖНА (SHALL) проектировать frontend runtime и gateway contract так, чтобы heavy background traffic одного staff-пользователя не starving'ил shell/bootstrap path и explicit interactive control traffic как normal behavior.

Это требование распространяется как на несколько tabs одного browser instance, так и на несколько одновременных browser sessions того же пользователя.

#### Scenario: Heavy route в одной tab не ломает shell bootstrap в другой
- **GIVEN** пользователь открыл `/pools/master-data?tab=sync`, и route запускает свой background-heavy data path
- **WHEN** в другой authenticated tab того же пользователя открывается staff route, которому нужен `/api/v2/system/bootstrap/`
- **THEN** shell bootstrap остаётся loadable через независимый request budget
- **AND** default path не считает `429` на bootstrap нормальным следствием heavy route в соседней tab

#### Scenario: Heavy route уменьшает свой own burst вместо надежды на shared shell budget
- **GIVEN** admin route известен как heavy background surface
- **WHEN** route проектируется для default operator path
- **THEN** secondary reads staged или consolidated так, чтобы route укладывался в свой documented background budget
- **AND** route не полагается на shared shell/control budget для успешной первичной загрузки
