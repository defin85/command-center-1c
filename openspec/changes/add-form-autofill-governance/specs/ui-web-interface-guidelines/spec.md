## ADDED Requirements
### Requirement: User-facing form controls MUST declare stable field identity and autofill semantics
Система ДОЛЖНА (SHALL) обеспечивать, что user-facing form controls на operator-facing frontend surfaces имеют стабильную field identity и явную browser autofill semantics.

Для `input`, `textarea`, `select`, AntD `Input`, `Input.Password`, `Input.TextArea` и эквивалентных platform field controls:
- field ДОЛЖЕН (SHALL) иметь stable `id` или `name`, либо использовать canonical platform wrapper, который задаёт их автоматически;
- field ДОЛЖЕН (SHALL) иметь `autocomplete`/`autoComplete` token, если его purpose относится к browser-autofillable данным;
- field ДОЛЖЕН (SHALL) быть явно classified as non-autofillable/domain control, если browser autofill не должен применяться;
- credential-like fields НЕ ДОЛЖНЫ (SHALL NOT) использовать generic `autocomplete="off"` как substitute для правильного token.

Accessible label contract остаётся обязательным: наличие `id`/`name`/`autocomplete` НЕ ДОЛЖНО (SHALL NOT) заменять label, `htmlFor`, `aria-label` или другой accessible-name path.

#### Scenario: Login field has identity, accessible name and autocomplete token
- **GIVEN** login или credential-like form показывает username/password field
- **WHEN** browser, password manager или accessibility tooling анализирует field
- **THEN** field has stable `id` or `name`
- **AND** field has correct `autocomplete` token such as `username`, `current-password`, `new-password` or `one-time-code`
- **AND** field still has accessible label or equivalent accessible name

#### Scenario: Operator domain field is explicitly non-autofillable
- **GIVEN** operator form содержит domain-specific field such as cluster id, operation reason, command parameter or pool selector
- **WHEN** browser autofill heuristics inspect the field
- **THEN** field identity remains stable for labels/testing/form tooling
- **AND** field intent explicitly marks it as domain/non-autofillable rather than leaving browser behavior implicit

#### Scenario: Composite control does not hide a user-facing field warning
- **GIVEN** user-facing control uses AntD `Select`, `AutoComplete`, `DatePicker` or another composite control
- **WHEN** final DOM contains internal input nodes
- **THEN** authored component boundary declares field intent and accessible name
- **AND** any runtime exception for vendor internal DOM is explicitly scoped and does not cover real user-facing missing metadata
