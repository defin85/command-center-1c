## ADDED Requirements

### Requirement: Workspace presentation eligibility MUST be declared explicitly in governance inventory

Система ДОЛЖНА (SHALL) требовать, чтобы любой route, который экспонирует или honor-ит shared workspace presentation preference, явно объявлял в governance inventory:
- allowed presentation modes;
- route default presentation mode.

Эти декларации ДОЛЖНЫ (SHALL) быть согласованы с `workspaceKind`, `detailMobileFallback` и `masterPaneGovernance`. Конфигурации, которые фактически переопределяют route family или нарушают route-level governance constraints, НЕ ДОЛЖНЫ (SHALL NOT) считаться валидными.

#### Scenario: Route без explicit presentation metadata не проходит governance validation

- **GIVEN** route implementation читает shared workspace presentation preference
- **AND** governance inventory не объявляет для него allowed/default presentation modes
- **WHEN** запускается frontend governance validation
- **THEN** validation сообщает явную ошибку о missing presentation eligibility declaration
- **AND** change не считается валидным до устранения конфликта

#### Scenario: Incompatible route family не может объявить presentation modes, меняющие canonical surface model

- **GIVEN** route относится к `workspaceKind`, который не поддерживает operator-selectable `catalog-detail` presentation variants
- **WHEN** implementation пытается объявить для него incompatible modes, меняющие canonical surface model
- **THEN** governance validation отклоняет такую конфигурацию
- **AND** route сохраняет свой canonical composition contract до отдельного approved change
