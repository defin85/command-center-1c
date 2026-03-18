## ADDED Requirements
### Requirement: Database realtime stream lease MUST быть scoped по client session, а не по пользователю целиком
Система ДОЛЖНА (SHALL) моделировать database realtime stream ownership через явную client session/lease модель, достаточную для различения как минимум:
- пользователя;
- browser/client instance;
- stream scope.

User-wide implicit singleton lease НЕ ДОЛЖЕН (SHALL NOT) оставаться единственной authoritative ownership model для default path.

#### Scenario: Вкладки одного браузера не конфликтуют между собой
- **GIVEN** один и тот же пользователь открыл две вкладки одного browser instance
- **AND** обе вкладки относятся к одной client session
- **WHEN** frontend поднимает database realtime path
- **THEN** system design использует один logical stream owner для этой client session
- **AND** вкладки НЕ ДОЛЖНЫ выбивать друг другу `429`/takeover как normal behavior

#### Scenario: Два независимых browser instance одного пользователя имеют явную session separation
- **GIVEN** один и тот же пользователь открыл приложение в двух независимых browser instance
- **WHEN** оба instance используют database realtime path
- **THEN** backend оценивает ownership как отдельные client sessions по явному contract
- **AND** конфликт или сосуществование stream'ов определяется этим session contract, а не неявным user-wide takeover

### Requirement: Default stream connect MUST быть conservative, а takeover MUST требовать явного recovery path
Система ДОЛЖНА (SHALL) трактовать `force`/takeover как explicit recovery behavior, а не как default connect policy.

Default path НЕ ДОЛЖЕН (SHALL NOT) молча вытеснять уже активного владельца stream lease. Если lease занят, система ДОЛЖНА (SHALL) вернуть fail-closed conflict response с machine-readable diagnostics.

#### Scenario: Fresh connect получает conflict вместо silent eviction
- **GIVEN** для той же session/scope уже существует активный stream owner
- **WHEN** новый transport пытается подключиться по default path
- **THEN** система возвращает conflict/`retry_after` contract
- **AND** existing owner НЕ вытесняется молча только из-за обычного повторного connect

#### Scenario: Явный recovery заменяет stale lease
- **GIVEN** operator или runtime recovery path явно инициировал takeover/recovery
- **AND** текущий lease признан stale или потерянным
- **WHEN** выполняется recovery connect
- **THEN** система может заменить существующий lease через documented explicit path
- **AND** replacement фиксируется как отдельное recovery событие, а не как обычный connect

### Requirement: Stream ticket и stream runtime MUST публиковать ownership/retry metadata для browser coordinator
Система ДОЛЖНА (SHALL) предоставлять browser coordinator machine-readable metadata, достаточную для предсказуемого reconnect/follower behavior.

Минимально это включает:
- session/lease identifier или эквивалентный ownership token;
- `retry_after` или эквивалентную подсказку cooldown/conflict window;
- достаточную информацию для resume/reconnect без blanket invalidation.

#### Scenario: Conflict response даёт coordinator actionable metadata
- **GIVEN** browser coordinator не может получить active stream lease по default path
- **WHEN** backend возвращает conflict
- **THEN** ответ содержит machine-readable ownership/retry metadata
- **AND** coordinator может принять детерминированное решение о cooldown, follower mode или explicit recovery

#### Scenario: Resume path сохраняет stream continuity
- **GIVEN** active browser coordinator временно теряет transport connection
- **WHEN** он выполняет reconnect/resume по documented path
- **THEN** session continuity и event resume выполняются через явный runtime contract
- **AND** клиент НЕ ДОЛЖЕН компенсировать reconnect blanket invalidation только из-за потери TCP/SSE соединения
