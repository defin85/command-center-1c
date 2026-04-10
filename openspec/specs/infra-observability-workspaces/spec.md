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

### Requirement: `/system-status` MUST provide deep-linkable runtime control drill-down for privileged operators
Система ДОЛЖНА (SHALL) сохранять `/system-status` canonical observability route и встраивать в него runtime control drill-down для privileged operators.

Runtime drill-down ДОЛЖЕН (SHALL) поддерживать:
- один canonical route-addressable selected runtime/service context без второго независимого selector path для diagnostics и controls;
- route-addressable selected tab (`Overview`, `Controls`, `Scheduler`, `Logs`);
- route-addressable selected scheduler job context;
- responsive fallback без page-wide overflow.

Mutating controls ДОЛЖНЫ (SHALL) использовать canonical secondary surfaces и НЕ ДОЛЖНЫ (SHALL NOT) требовать raw browser prompts как primary path.

#### Scenario: Deep-link восстанавливает runtime control context
- **GIVEN** staff оператор открывает `/system-status` с выбранными `service=worker-workflows`, `tab=scheduler` и `job=pool_factual_active_sync`
- **WHEN** страница перезагружается или открывается по deep-link
- **THEN** workspace восстанавливает тот же runtime control context
- **AND** оператор может перейти между `Overview`, `Controls`, `Scheduler` и `Logs` без page-wide overflow

#### Scenario: Пользователь без runtime-control capability видит diagnostics-only workspace
- **GIVEN** аутентифицированный пользователь не имеет runtime-control capability
- **WHEN** он открывает `/system-status`
- **THEN** diagnostics surface остаётся доступной
- **AND** mutating runtime/scheduler controls скрыты или недоступны

