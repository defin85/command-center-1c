## ADDED Requirements

### Requirement: Scheme-specific pool intake surfaces MUST reuse platform mechanics without forcing every scheme into one generic drawer

Для high-ceremony pool intake schemes, где оператор вводит domain-specific parameters rather than uploading an external registry, система ДОЛЖНА (SHALL) use a scheme-specific operator surface module backed by shared pool intake mechanics.

The shared mechanics SHALL include pool/period context, workflow binding selection and compatibility diagnostics, preview/create-run lifecycle, generated API clients, i18n boundaries, and platform shell primitives.

The scheme-specific module SHALL own only domain-specific controls, preview composition, and blocked-submit rules for that scheme.

The generic batch intake drawer MUST NOT become the primary owner of unrelated scheme-specific authoring flows through accumulating `scheme_code` conditionals when a scheme requires its own parameter model, preview evidence, or staged publication controls.

#### Scenario: KVO17 generator uses custom controls while reusing shared intake mechanics
- **GIVEN** operator opens KVO17 generated purchase mode
- **WHEN** the UI renders the generator
- **THEN** the operator sees structured controls for counterparties, amount ranges, KVO assignment, seed, preview, and create-run
- **AND** the UI reuses the shared pool, period, binding, diagnostics, API lifecycle, and platform shell mechanics
- **AND** the operator is not required to author the generated request as raw JSON in the generic schema-template payload textarea

#### Scenario: Unsupported scheme does not add ad hoc controls to the generic drawer
- **GIVEN** a future pool scheme requires a materially different operator parameter model
- **WHEN** frontend support is added for that scheme
- **THEN** the implementation provides a scheme-specific module or route surface
- **AND** shared lifecycle and binding mechanics remain reusable through an explicit registry/shell boundary
- **AND** the generic drawer does not gain another unrelated set of hardcoded authoring controls
