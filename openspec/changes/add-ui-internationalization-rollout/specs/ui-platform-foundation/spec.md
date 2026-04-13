## ADDED Requirements

### Requirement: Thin design layer MUST provide localized shared semantics for migrated route families and shell-backed surfaces

Система ДОЛЖНА (SHALL) держать в thin design layer locale-aware shared semantics для page chrome, empty/error/status primitives, JSON/detail helpers и shell-backed `DrawerForm`/`ModalForm` surfaces, чтобы migrated route families могли переиспользовать один canonical path вместо route-local string ownership.

Platform primitives и shell-backed surfaces НЕ ДОЛЖНЫ (SHALL NOT) требовать ad hoc route-level override tables для той operator-facing copy, которой уже владеет thin design layer как shared semantic contract.

#### Scenario: Migrated route reuses platform primitives without rebuilding shared copy ownership

- **GIVEN** команда мигрирует remaining platform-governed route family на canonical i18n path
- **WHEN** route использует `PageHeader`, `EmptyState`, `StatusBadge`, `JsonBlock`, `DrawerFormShell` или `ModalFormShell`
- **THEN** shared primitive copy и locale-aware formatting приходят из thin design layer через canonical namespaces и formatter layer
- **AND** route не создаёт новый route-local shared-copy registry только ради повторения platform semantics

#### Scenario: Shell-backed editor stays locale-consistent with the page chrome

- **GIVEN** migrated route открывает editor drawer или modal через platform shell primitive
- **WHEN** shell locale переключён между `ru` и `en`
- **THEN** page chrome и editor surface используют один и тот же effective locale и shared semantic vocabulary
- **AND** пользователь не сталкивается с mixed-language split между route header и shell-backed editor
