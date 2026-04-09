## ADDED Requirements

### Requirement: `MasterDetail` platform primitives MUST support approved wide-viewport presentation variants

Система ДОЛЖНА (SHALL) позволять canonical `MasterDetail` platform primitives рендерить approved wide-viewport presentation variants для одного и того же compatible route, когда governance inventory явно разрешает такие mode values.

Поддержка wide-viewport `drawer` variant НЕ ДОЛЖНА (SHALL NOT) отменять existing narrow-viewport mobile-safe fallback и НЕ ДОЛЖНА (SHALL NOT) вводить page-wide horizontal overflow как primary access path к detail surface.

#### Scenario: Wide viewport route использует drawer-backed detail как approved variant

- **GIVEN** compatible `catalog-detail` route объявляет allowed presentation modes `auto`, `split` и `drawer`
- **AND** effective mode для route разрешён как `drawer`
- **WHEN** оператор выбирает элемент каталога на wide viewport
- **THEN** list остаётся primary workspace surface
- **AND** detail открывается через canonical secondary surface внутри того же route contract
- **AND** route не переопределяется в другой `workspaceKind`

#### Scenario: Responsive fallback остаётся сильнее desktop preference

- **GIVEN** compatible route поддерживает `split` на wide viewport
- **WHEN** тот же route открывается на narrow viewport
- **THEN** `MasterDetail` primitive использует mobile-safe fallback для detail
- **AND** реализация не требует dual-column layout как единственного способа доступа к inspect surface
