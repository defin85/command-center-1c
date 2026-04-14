## ADDED Requirements

### Requirement: Legacy-monitored factual workspace MUST graduate into inventory-backed locale governance before migration completion

Система НЕ ДОЛЖНА (SHALL NOT) считать `/pools/factual` migrated на canonical i18n path, если route entry или его checked-in shell surfaces остаются `legacy-monitored` в governance inventory и обходят generic locale-boundary validation gates.

Для completion этого change система ДОЛЖНА (SHALL):
- классифицировать factual route/shell modules в checked-in inventory так, чтобы на них распространялись inventory-backed locale governance checks;
- блокировать formatter/locale-boundary regressions для factual slice теми же generic lint/test gates, что и для других migrated operator-facing surfaces;
- избегать bespoke one-off allowlist/rule path, нужного только для того, чтобы считать factual route "особым случаем".

#### Scenario: Factual route cannot stay legacy-monitored after i18n migration

- **GIVEN** код factual workspace уже переведён на canonical translation hooks и shared formatters
- **WHEN** в checked-in governance inventory `/pools/factual` или его shell surface всё ещё помечены как `legacy-monitored`
- **THEN** locale governance completion считается незавершённой
- **AND** validation gate требует явной inventory graduation вместо молчаливого исключения

#### Scenario: Factual modal inherits governance coverage from inventory

- **GIVEN** `PoolFactualReviewAttributeModal.tsx` принадлежит `/pools/factual` и открывается как route-owned shell surface
- **WHEN** разработчик нарушает canonical locale boundary внутри этого modal surface
- **THEN** lint или related governance test сообщает нарушение через generic inventory-backed coverage
- **AND** команде не нужен отдельный bespoke factual-only enforcement path, чтобы поймать regression
