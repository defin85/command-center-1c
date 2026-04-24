## 1. Contract and policy
- [ ] 1.1 Define checked-in form field purpose/autocomplete policy for platform-owned form primitives and governed route/shell modules.
- [ ] 1.2 Add or update platform form primitive API so new fields can declare purpose, stable identity and autocomplete semantics without hand-written boilerplate.
- [ ] 1.3 Define narrow checked-in allowlist format for vendor/internal composite fields with required reason and owning surface.

## 2. Static governance
- [ ] 2.1 Extend `ui-platform-local` ESLint plugin with form field identity/autocomplete governance rules.
- [ ] 2.2 Enforce rules on platform primitives and inventory-backed governed route/shell modules; keep legacy exceptions explicit.
- [ ] 2.3 Add focused `UiPlatformGovernanceLint.test.ts` coverage for missing `id`/`name`, missing `autoComplete`, forbidden credential `autoComplete="off"`, valid platform wrapper usage and scoped vendor/internal exception.

## 3. Runtime browser audit
- [ ] 3.1 Expand `frontend/tests/browser/form-field-ids.spec.ts` into a form field governance browser audit that reports route/surface, selector, field type and violation reason.
- [ ] 3.2 Include visible/enabled fields inside AntD portal modal/drawer containers.
- [ ] 3.3 Integrate Chrome DevTools Protocol `Audits.checkFormsIssues` when available, with deterministic fallback DOM checks when not available.
- [ ] 3.4 Add or update browser coverage for at least one credential/auth-like form and one operator/domain form with AntD composite controls.

## 4. Pilot remediation
- [ ] 4.1 Remediate the highest-risk credential/auth/admin connection fields first with explicit `id`, `name` and correct `autoComplete` tokens.
- [ ] 4.2 Remediate or explicitly classify pilot operator/domain controls that trigger current DevTools warnings.
- [ ] 4.3 Keep AntD internal fields out of user-facing debt counts only through scoped allowlist entries.

## 5. Validation
- [ ] 5.1 Run `cd frontend && npm run lint`.
- [ ] 5.2 Run focused governance lint tests for form field rules.
- [ ] 5.3 Run `cd frontend && npm run test:browser:forms`.
- [ ] 5.4 Run affected targeted route tests for remediated surfaces.
- [ ] 5.5 Run `openspec validate add-form-autofill-governance --strict --no-interactive`.
