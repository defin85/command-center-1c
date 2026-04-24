# Change: Form autofill governance for frontend fields

## Why
Chrome DevTools уже показывает autofill/form issues на наших страницах: часть form controls не имеет стабильного `id`/`name`, а часть распознаётся браузером как autofill-relevant field без явного `autocomplete`.

Сейчас это ловится поздно и фрагментарно: есть browser smoke `frontend/tests/browser/form-field-ids.spec.ts`, но он проверяет ограниченный набор route path, не покрывает `autocomplete`, не различает AntD internal controls и user-facing fields, и не задаёт checked-in contract для новых компонентов.

Нужно поднять это в governance layer: field intent должен быть явным в коде, statically проверяемым для наших JSX/Form components и runtime-проверяемым для DOM, который генерирует AntD.

## What Changes
- Добавить frontend governance contract для form field identity, autofill intent и `autocomplete` semantics.
- Ввести checked-in field-purpose/autocomplete policy для platform-owned form primitives и migrated/governed modules.
- Расширить local ESLint governance так, чтобы новые governed form fields не могли появиться без field intent, stable identity и корректного `autoComplete`.
- Расширить browser-level form audit, чтобы он ловил Chrome/DOM autofill issues на governed routes и portal-based modal/drawer surfaces.
- Добавить narrow allowlist только для известных AntD composite/internal inputs, где raw DOM field не является самостоятельным user-facing form field.

## Impact
- Affected specs:
  - `ui-frontend-governance`
  - `ui-web-interface-guidelines`
- Affected code:
  - `frontend/eslint.config.js`
  - `frontend/src/components/platform/**`
  - `frontend/src/uiGovernanceInventory.js`
  - `frontend/src/components/platform/__tests__/UiPlatformGovernanceLint.test.ts`
  - `frontend/tests/browser/form-field-ids.spec.ts`
  - selected form-heavy route modules using `Form.Item`, `Input`, `Input.Password`, `Input.TextArea`, `Select`, `AutoComplete`, `DatePicker`, `InputNumber`
- Affected validation:
  - `cd frontend && npm run lint`
  - `cd frontend && npm run test:run -- src/components/platform/__tests__/UiPlatformGovernanceLint.test.ts`
  - `cd frontend && npm run test:browser:forms`
  - targeted route/browser tests for any fixed form-heavy surface

## Non-Goals
- Big-bang cleanup of every historical AntD field in the repository.
- Replacing AntD form internals or forking vendor components.
- Treating `autocomplete="off"` as a security boundary for credentials.
- Adding browser autofill credential storage tests; this change is about markup contract and detection.
