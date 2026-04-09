# infra-observability-workspaces Specification

## Purpose
TBD - created by archiving change 04-refactor-ui-platform-infra-observability-workspaces. Update Purpose after archive.
## Requirements
### Requirement: `/clusters` MUST использовать canonical cluster management workspace
Система ДОЛЖНА (SHALL) представлять `/clusters` как management workspace с route-addressable selected cluster/filter context и canonical secondary surfaces для create/edit/discover/credentials flows.

#### Scenario: Cluster workspace восстанавливает selected cluster context из URL
- **GIVEN** оператор открывает `/clusters` с query state, указывающим фильтры и выбранный cluster
- **WHEN** страница перезагружается или открывается по deep-link
- **THEN** workspace восстанавливает тот же cluster context
- **AND** primary mutating flows используют canonical secondary surfaces внутри platform workspace

### Requirement: `/system-status` MUST использовать canonical observability workspace
Система ДОЛЖНА (SHALL) представлять `/system-status` как observability workspace с route-addressable diagnostics context, controlled polling state и responsive fallback для service inspection.

#### Scenario: System status workspace сохраняет diagnostics context без page-wide overflow
- **GIVEN** оператор открыл `/system-status` и выбрал diagnostics context или ручной refresh path
- **WHEN** страница работает на узком viewport или после reload
- **THEN** observability flow остаётся доступным внутри canonical workspace shell
- **AND** UI не зависит от raw dashboard grid как единственного route-level foundation

### Requirement: `/service-mesh` MUST использовать canonical realtime observability workspace
Система ДОЛЖНА (SHALL) представлять `/service-mesh` как realtime observability workspace с platform-owned shell и responsive fallback для topology/metrics inspection.

#### Scenario: Service mesh route использует platform shell вместо bespoke page wrapper
- **GIVEN** оператор открывает `/service-mesh`
- **WHEN** route рендерит realtime topology and metrics surface
- **THEN** page shell проходит через canonical platform primitives
- **AND** topology/metrics inspection остаётся доступным на narrow viewport без bespoke full-page wrapper как единственного layout path

