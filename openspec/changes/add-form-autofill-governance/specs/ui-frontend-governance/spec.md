## ADDED Requirements
### Requirement: Form field autofill governance MUST be enforced through static and browser-level checks
Система ДОЛЖНА (SHALL) выражать frontend form field identity, autofill intent и `autocomplete` semantics через checked-in governance policy и blocking automated checks.

Governed user-facing form controls ДОЛЖНЫ (SHALL) иметь стабильную identity для browser/form tooling через `id`, `name` или canonical platform wrapper, который генерирует эти attributes предсказуемо.

Governed user-facing form controls ДОЛЖНЫ (SHALL) иметь явный autofill intent:
- browser-autofillable credential/contact fields ДОЛЖНЫ (SHALL) использовать корректный `autocomplete` token;
- operator/domain controls, где browser autofill не нужен, ДОЛЖНЫ (SHALL) быть явно классифицированы как non-autofillable/domain control;
- vendor/internal composite inputs ДОЛЖНЫ (SHALL) попадать только в checked-in scoped allowlist с reason, если final DOM невозможно исправить на authored component boundary.

Static governance checks ДОЛЖНЫ (SHALL) ловить authored JSX violations там, где это надёжно: missing field identity, missing autocomplete on recognized autofill fields, forbidden generic `autocomplete="off"` for credential-like fields and missing field intent on governed `Form.Item` paths.

Browser-level governance checks ДОЛЖНЫ (SHALL) ловить final DOM violations, включая AntD-generated fields and portal-based modal/drawer controls, and report actionable route/surface context instead of anonymous violating-node counts.

#### Scenario: New governed input without identity fails lint
- **GIVEN** разработчик добавляет user-facing `Input` или native `input` в governed route/shell module
- **WHEN** field не имеет stable `id`/`name` и не проходит через canonical platform field primitive
- **THEN** frontend lint сообщает form field identity violation
- **AND** изменение не проходит validation gate

#### Scenario: Credential field without explicit autocomplete fails lint
- **GIVEN** governed form field имеет `id`, `name` или purpose, который соответствует username/password/email/OTP credential class
- **WHEN** field не задаёт корректный `autoComplete` token
- **THEN** static governance check сообщает missing autocomplete violation
- **AND** generic `autoComplete="off"` не считается достаточным для credential-like field

#### Scenario: Browser form audit catches generated DOM issue
- **GIVEN** governed page или drawer/modal surface рендерит final DOM через AntD composite controls
- **WHEN** visible/enabled form field в final DOM не имеет `id`/`name` или распознаётся browser autofill heuristics без `autocomplete`
- **THEN** browser-level governance test reports route/surface, selector, field type and violation reason
- **AND** validation gate fails unless the node is covered by a scoped checked-in vendor/internal allowlist

#### Scenario: Vendor internal field exception is narrow and justified
- **GIVEN** AntD composite control создаёт internal search input, который не является самостоятельным user-facing field
- **WHEN** browser audit видит DOM node, похожий на form field violation
- **THEN** exception accepted only if a checked-in allowlist entry names the component/surface and reason
- **AND** broad wildcard allowlist does not satisfy governance
