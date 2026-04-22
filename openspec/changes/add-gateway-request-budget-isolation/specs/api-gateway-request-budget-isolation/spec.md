## ADDED Requirements

### Requirement: Gateway request budgets MUST be isolated by workload class
Система ДОЛЖНА (SHALL) применять rate limiting к authenticated API traffic не как к одному undifferentiated per-user bucket, а как минимум по workload classes:
- `shell_critical`
- `interactive`
- `background_heavy`
- `telemetry`

Streaming/ticket endpoints МОГУТ (MAY) оставаться отдельным special-case path, но shared bucket для shell/bootstrap и heavy background reads НЕ ДОЛЖЕН (SHALL NOT) оставаться default architecture.

#### Scenario: Heavy background route не starving'ит shell bootstrap другого route
- **GIVEN** staff-пользователь уже держит открытую heavy background route, расходующую `background_heavy` budget
- **WHEN** тот же пользователь открывает другую authenticated tab/session, которая запрашивает `/api/v2/system/bootstrap/`
- **THEN** bootstrap request оценивается по независимому `shell_critical` budget
- **AND** `429` для bootstrap НЕ является normal behavior только из-за background-heavy traffic того же пользователя

#### Scenario: Telemetry overflow не расходует shell budget
- **GIVEN** browser отправляет bursts на `/api/v2/ui/incident-telemetry/ingest/`
- **WHEN** telemetry budget исчерпан
- **THEN** gateway ограничивает telemetry в её собственном budget class
- **AND** этот overflow не уменьшает budget, доступный для shell-critical requests

### Requirement: Gateway route-to-budget classification MUST be explicit and bounded
Система ДОЛЖНА (SHALL) иметь explicit checked-in mapping или эквивалентный contract, который определяет `budget_class` для gateway-handled routes.

Route без явной special classification НЕ ДОЛЖЕН (SHALL NOT) попадать в unlimited path по умолчанию. Unknown или newly-added route ДОЛЖЕН (SHALL) резолвиться в documented bounded default class.

#### Scenario: Новый route не становится unlimited из-за отсутствия classification
- **GIVEN** в gateway добавлен новый `/api/v2` route без отдельного exemption
- **WHEN** route регистрируется в runtime
- **THEN** он получает documented bounded default `budget_class`
- **AND** route не bypass'ит rate limiting молча

### Requirement: Gateway 429 responses MUST expose machine-readable budget metadata
Система ДОЛЖНА (SHALL) возвращать для gateway-generated `429` ошибки machine-readable metadata, достаточную для deterministic UI/backoff/incident handling.

Минимально ответ ДОЛЖЕН (SHALL) содержать:
- `rate_limit_class`
- `retry_after_seconds`
- `budget_scope`
- correlation fields, совместимые с существующим error contract

#### Scenario: UI получает actionable 429 contract
- **GIVEN** gateway отклоняет request по budget exhaustion
- **WHEN** клиент получает HTTP `429`
- **THEN** response payload содержит `rate_limit_class` и `retry_after_seconds`
- **AND** клиент и diagnostics tooling могут отличить shell starvation от telemetry/background overflow

### Requirement: Gateway rate-limit configuration MUST have one runtime source of truth
Система ДОЛЖНА (SHALL) иметь один authoritative runtime config surface для budget classes и их числовых лимитов.

Checked-in config artifact и runtime loader НЕ ДОЛЖНЫ (SHALL NOT) расходиться так, что один surface декларирует rate-limit settings, а production code их игнорирует.

#### Scenario: Checked-in budget config соответствует runtime behavior
- **GIVEN** инженер изменяет checked-in budget configuration для gateway
- **WHEN** runtime стартует и tests проверяют effective settings
- **THEN** gateway использует именно этот authoritative config path
- **AND** drift между checked-in config и runtime behavior детектируется automated checks
