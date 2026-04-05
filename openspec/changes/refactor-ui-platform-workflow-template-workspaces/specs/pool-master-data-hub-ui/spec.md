## ADDED Requirements
### Requirement: `/pools/master-data` MUST использовать canonical multi-zone workspace shell
Система ДОЛЖНА (SHALL) представлять `/pools/master-data` как canonical multi-zone workspace с route-addressable active tab/remediation context и responsive fallback для zone-specific inspect/edit flows.

Этот requirement управляет page foundation, URL state и responsive inspect/edit contract для workspace shell; domain-specific расширение reusable-account surfaces может поставляться отдельным post-platform change поверх этого foundation.

#### Scenario: Master-data workspace восстанавливает tab и remediation context из URL
- **GIVEN** оператор открывает `/pools/master-data` с query state, указывающим активный tab и remediation context
- **WHEN** страница перезагружается или открывается по deep-link
- **THEN** workspace восстанавливает тот же tab/remediation context
- **AND** operator flow остаётся внутри platform-owned shell без raw tab canvas как единственного page-level foundation
