## MODIFIED Requirements
### Requirement: Plan set_flags принимает apply_mask
Система ДОЛЖНА (SHALL) принимать `apply_mask` в `POST /api/v2/extensions/plan/` для `capability="extensions.set_flags"` только из runtime request/input и НЕ ДОЛЖНА (SHALL NOT) использовать capability/action preset как fallback.

#### Scenario: apply_mask обязателен и берётся только из request
- **GIVEN** вызывается `POST /api/v2/extensions/plan/` для `extensions.set_flags`
- **WHEN** в request отсутствует `apply_mask`
- **THEN** backend возвращает `HTTP 400` с `VALIDATION_ERROR`
- **AND** plan не создаётся

#### Scenario: preset apply_mask в action игнорируется и запрещён
- **GIVEN** action `extensions.set_flags` содержит `executor.fixed.apply_mask` или exposure-level `capability_config.apply_mask`
- **WHEN** вызывается `POST /api/v2/extensions/plan/`
- **THEN** backend не использует этот preset как runtime source
- **AND** backend возвращает `CONFIGURATION_ERROR` до preview/execute

### Requirement: Детерминированный выбор action через action_id
Система ДОЛЖНА (SHALL) требовать `action_id` для `extensions.set_flags` и НЕ ДОЛЖНА (SHALL NOT) выполнять неявный выбор action только по `capability`.

#### Scenario: Отсутствует action_id для set_flags
- **GIVEN** request для `extensions.set_flags` без `action_id`
- **WHEN** вызывается `POST /api/v2/extensions/plan/`
- **THEN** backend возвращает `HTTP 400` с `MISSING_PARAMETER` (action_id is required)
- **AND** plan не создаётся

## ADDED Requirements
### Requirement: `extensions.set_flags` MUST использовать runtime `flags_values` как единственный источник значений
Система ДОЛЖНА (SHALL) для `extensions.set_flags` принимать значения флагов из request/input (`flags_values`) и подставлять их в executor через `$flags.*` токены.

#### Scenario: Runtime values подставляются в executor params
- **GIVEN** request содержит `flags_values` и `apply_mask`
- **AND** action `extensions.set_flags` использует `$flags.active`, `$flags.safe_mode`, `$flags.unsafe_action_protection`
- **WHEN** вызывается `POST /api/v2/extensions/plan/`
- **THEN** backend строит effective params только из runtime `flags_values`
- **AND** не использует policy/preset source для резолва значений
